"""Locate, read, and clean UNSW-NB15 files (both the partitioned and full-record families)."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from sentinel_ml.features.cleaning import CleanResult, SchemaError, clean_frame
from sentinel_ml.schema import (
    ALL_FEATURES,
    CATEGORY_COLUMN,
    FEATURES_DESCRIPTION_FILE,
    FULL_RECORD_COLUMNS,
    LABEL_COLUMN,
    SYNTHETIC_MARKER_FILE,
    normalize_column_name,
)

SchemaKind = Literal["unsw_partitioned", "unsw_full"]
DataOrigin = Literal["unsw-nb15", "synthetic"]

DEFAULT_CHUNK_ROWS = 200_000


class DatasetError(Exception):
    """A dataset file is missing, unreadable, or does not match the expected schema."""


@dataclass(frozen=True)
class SourceFile:
    name: str
    sha256: str
    size_bytes: int


@dataclass
class LoadedDataset:
    features: pd.DataFrame
    labels: pd.Series
    metadata: pd.DataFrame
    schema_kind: SchemaKind
    origin: DataOrigin
    sources: list[SourceFile]
    rows_read: int
    rejection_counts: Counter[str] = field(default_factory=Counter)
    metadata_issues: Counter[str] = field(default_factory=Counter)

    @property
    def rows_rejected(self) -> int:
        return self.rows_read - len(self.features)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def data_origin(data_dir: Path) -> DataOrigin:
    return "synthetic" if (data_dir / SYNTHETIC_MARKER_FILE).exists() else "unsw-nb15"


def find_file(data_dir: Path, name: str) -> Path:
    """Find ``name`` in ``data_dir`` (case-insensitive; downloads are sometimes renamed)."""
    if not data_dir.is_dir():
        raise DatasetError(f"Data directory not found: {data_dir}")
    for candidate in data_dir.iterdir():
        if candidate.is_file() and candidate.name.lower() == name.lower():
            return candidate
    raise DatasetError(
        f"{name} not found in {data_dir}. See ml/data/README.md for download instructions."
    )


def _first_line(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        row = next(csv.reader(handle), None)
    if not row:
        raise DatasetError(f"{path.name} is empty")
    return row


def detect_schema(path: Path) -> SchemaKind:
    """Partitioned files have a header row; full-record files have none and 49 columns."""
    first = [normalize_column_name(cell) for cell in _first_line(path)]
    # Header detection only needs the label columns; clean_frame then reports any missing
    # feature columns by name.
    if CATEGORY_COLUMN in first or LABEL_COLUMN in first:
        return "unsw_partitioned"
    if len(first) == len(FULL_RECORD_COLUMNS):
        return "unsw_full"
    raise DatasetError(
        f"{path.name}: unrecognised layout ({len(first)} columns, no UNSW-NB15 header)"
    )


def full_record_columns(data_dir: Path | None) -> list[str]:
    """Column names for header-less files, read from NUSW-NB15_features.csv when present."""
    if data_dir is not None:
        try:
            description = find_file(data_dir, FEATURES_DESCRIPTION_FILE)
        except DatasetError:
            description = None
        if description is not None:
            table = pd.read_csv(description, encoding="latin-1")
            name_column = next((c for c in table.columns if str(c).strip().lower() == "name"), None)
            if name_column is None:
                raise DatasetError(f"{description.name} has no 'Name' column")
            names = [normalize_column_name(str(n)) for n in table[name_column]]
            if names != list(FULL_RECORD_COLUMNS):
                raise DatasetError(
                    f"{description.name} lists columns that differ from the expected schema: "
                    f"{names}"
                )
            return names
    return list(FULL_RECORD_COLUMNS)


def labels_of(result: CleanResult) -> pd.Series:
    if result.labels is None:  # only possible if called without require_labels=True
        raise RuntimeError("Labels were not requested from clean_frame")
    return result.labels


def iter_raw_chunks(
    path: Path, kind: SchemaKind, data_dir: Path | None, chunk_rows: int = DEFAULT_CHUNK_ROWS
) -> Iterator[pd.DataFrame]:
    """Yield raw string-typed chunks so every value is validated by the same code."""
    options: dict[str, object] = {
        "dtype": str,
        "keep_default_na": False,
        "chunksize": chunk_rows,
        "encoding": "utf-8",
        "encoding_errors": "replace",
    }
    if kind == "unsw_full":
        options.update(header=None, names=full_record_columns(data_dir))
    try:
        with pd.read_csv(path, **options) as reader:  # type: ignore[call-overload]
            yield from reader
    except (pd.errors.ParserError, UnicodeError) as exc:
        raise DatasetError(f"{path.name}: could not parse CSV ({exc.__class__.__name__})") from exc


def load_files(
    paths: Iterable[Path],
    *,
    data_dir: Path | None = None,
    required_features: Iterable[str] = ALL_FEATURES,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
) -> LoadedDataset:
    """Load and clean labelled UNSW-NB15 files of one schema family."""
    paths = list(paths)
    if not paths:
        raise DatasetError("No dataset files given")
    required = list(required_features)
    kinds = {detect_schema(p) for p in paths}
    if len(kinds) != 1:
        raise DatasetError("Cannot mix partitioned and full-record files in one load")
    kind = kinds.pop()

    feature_parts: list[pd.DataFrame] = []
    label_parts: list[pd.Series] = []
    metadata_parts: list[pd.DataFrame] = []
    rejections: Counter[str] = Counter()
    metadata_issues: Counter[str] = Counter()
    rows_read = 0
    for path in paths:
        for chunk in iter_raw_chunks(path, kind, data_dir, chunk_rows):
            rows_read += len(chunk)
            try:
                result = clean_frame(chunk, required, require_labels=True)
            except SchemaError as exc:
                raise DatasetError(f"{path.name}: {exc}") from exc
            feature_parts.append(result.features)
            label_parts.append(labels_of(result))
            metadata_parts.append(result.metadata)
            rejections.update(result.rejection_counts)
            metadata_issues.update(result.metadata_issues)

    if rows_read == 0:
        raise DatasetError("Dataset files contain no data rows")

    origin_dirs = {p.parent for p in paths}
    origins = {data_origin(d) for d in origin_dirs}
    return LoadedDataset(
        features=pd.concat(feature_parts, ignore_index=True),
        labels=pd.concat(label_parts, ignore_index=True).rename(LABEL_COLUMN),
        metadata=pd.concat(metadata_parts, ignore_index=True),
        schema_kind=kind,
        origin="synthetic" if "synthetic" in origins else "unsw-nb15",
        sources=[SourceFile(p.name, sha256_file(p), p.stat().st_size) for p in paths],
        rows_read=rows_read,
        rejection_counts=rejections,
        metadata_issues=metadata_issues,
    )
