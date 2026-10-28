"""Profile the real UNSW-NB15 files before any modelling decision depends on them.

Reports actual columns, inferred types, blank values, label distributions (raw and
normalised), validation rejections, duplicates, train/test overlap, and IP availability.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sentinel_ml.features.cleaning import clean_frame, normalize_columns
from sentinel_ml.features.dataset import (
    DatasetError,
    data_origin,
    detect_schema,
    find_file,
    iter_raw_chunks,
    labels_of,
    sha256_file,
)
from sentinel_ml.schema import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    CATEGORY_COLUMN,
    FULL_RECORD_COLUMNS,
    FULL_RECORD_FILES,
    LABEL_COLUMN,
    PARTITIONED_COLUMNS,
    TEST_FILE,
    TRAIN_FILE,
)

TOP_VALUES = 25

logger = logging.getLogger(__name__)


def _profile_file(path: Path, data_dir: Path) -> tuple[dict[str, Any], np.ndarray]:
    kind = detect_schema(path)
    expected = PARTITIONED_COLUMNS if kind == "unsw_partitioned" else FULL_RECORD_COLUMNS
    rows = 0
    columns: list[str] = []
    blank: Counter[str] = Counter()
    non_numeric: Counter[str] = Counter()
    raw_values: dict[str, Counter[str]] = {
        c: Counter() for c in (*CATEGORICAL_FEATURES, CATEGORY_COLUMN, LABEL_COLUMN)
    }
    normalised_labels: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    metadata_issues: Counter[str] = Counter()
    ip_present = {"src_ip": 0, "dst_ip": 0}
    time_range: list[pd.Timestamp] = []
    row_hashes: list[np.ndarray] = []

    for chunk in iter_raw_chunks(path, kind, data_dir):
        chunk = normalize_columns(chunk)
        columns = list(chunk.columns)
        rows += len(chunk)
        for column in columns:
            text = chunk[column].str.strip()
            is_blank = text == ""
            blank[column] += int(is_blank.sum())
            parsed = pd.to_numeric(text.where(~is_blank), errors="coerce")
            non_numeric[column] += int((~is_blank & parsed.isna()).sum())
            if column in raw_values:
                # repr() keeps leading/trailing whitespace visible in the report.
                raw_values[column].update(repr(v) for v in chunk[column])

        result = clean_frame(chunk, ALL_FEATURES, require_labels=True)
        labels = labels_of(result)
        normalised_labels.update(labels.tolist())
        rejections.update(result.rejection_counts)
        metadata_issues.update(result.metadata_issues)
        for column in ip_present:
            ip_present[column] += int(result.metadata[column].notna().sum())
        for column in ("start_time", "last_time"):
            series = result.metadata[column].dropna()
            if not series.empty:
                time_range += [series.min(), series.max()]
        frame = result.features[list(ALL_FEATURES)].assign(_label=labels.to_numpy())
        row_hashes.append(pd.util.hash_pandas_object(frame, index=False).to_numpy())

    hashes = np.concatenate(row_hashes) if row_hashes else np.array([], dtype=np.uint64)
    numeric_like = {c for c in columns if non_numeric[c] == 0}
    profile = {
        "file": path.name,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "schema_kind": kind,
        "rows": rows,
        "columns": columns,
        "missing_expected_columns": [c for c in expected if c not in columns],
        "unexpected_columns": [c for c in columns if c not in expected],
        "column_types": {c: ("numeric" if c in numeric_like else "text") for c in columns},
        "blank_values": {c: blank[c] for c in columns if blank[c]},
        "non_numeric_values": {c: non_numeric[c] for c in columns if c not in numeric_like},
        "raw_value_counts": {c: dict(v.most_common(TOP_VALUES)) for c, v in raw_values.items()},
        "distinct_raw_values": {c: len(v) for c, v in raw_values.items()},
        "label_distribution": dict(normalised_labels.most_common()),
        "rows_valid": len(hashes),
        "rejection_counts": dict(rejections),
        "metadata_issues": dict(metadata_issues),
        "duplicate_rows": int(len(hashes) - len(np.unique(hashes))),
        "ip_available_rows": ip_present,
        "time_range_utc": (
            [min(time_range).isoformat(), max(time_range).isoformat()] if time_range else None
        ),
    }
    return profile, np.unique(hashes)


def profile_dataset(data_dir: Path) -> dict[str, Any]:
    present = []
    for name in (TRAIN_FILE, TEST_FILE, *FULL_RECORD_FILES):
        try:
            present.append(find_file(data_dir, name))
        except DatasetError:
            continue
    if not present:
        raise DatasetError(
            f"No UNSW-NB15 files found in {data_dir}. See ml/data/README.md for instructions."
        )

    files = []
    unique_hashes: dict[str, np.ndarray] = {}
    for path in present:
        logger.info("Profiling %s", path.name)
        profile, hashes = _profile_file(path, data_dir)
        files.append(profile)
        unique_hashes[path.name] = hashes

    overlap = None
    if TRAIN_FILE in unique_hashes and TEST_FILE in unique_hashes:
        overlap = int(np.isin(unique_hashes[TEST_FILE], unique_hashes[TRAIN_FILE]).sum())
    return {
        "data_origin": data_origin(data_dir),
        "files": files,
        "distinct_test_rows_also_in_train": overlap,
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    out = ["# UNSW-NB15 data profile", ""]
    if profile["data_origin"] == "synthetic":
        out += ["> **SYNTHETIC DATA — NOT UNSW-NB15.** Do not quote these figures.", ""]
    out += [
        "Generated by `sentinel-ml profile` from the files actually present in the data",
        "directory. Raw values are shown with `repr()` so stray whitespace is visible.",
        "",
    ]
    if profile["distinct_test_rows_also_in_train"] is not None:
        out += [
            f"Distinct testing-set rows (features + label) also present in the training set: "
            f"**{profile['distinct_test_rows_also_in_train']}**",
            "",
        ]
    for f in profile["files"]:
        out += [
            f"## {f['file']}",
            "",
            f"- Layout: `{f['schema_kind']}`; size {f['size_bytes']} bytes; "
            f"SHA-256 `{f['sha256']}`",
            f"- Rows: {f['rows']}; valid after validation: {f['rows_valid']}; "
            f"duplicate valid rows: {f['duplicate_rows']}",
            f"- Columns ({len(f['columns'])}): `{', '.join(f['columns'])}`",
            f"- Missing expected columns: `{f['missing_expected_columns'] or 'none'}`",
            f"- Unexpected columns: `{f['unexpected_columns'] or 'none'}`",
            f"- Text-typed columns: `{f['non_numeric_values'] or 'none'}`",
            f"- Blank values: `{f['blank_values'] or 'none'}`",
            f"- Rejected rows by reason: `{f['rejection_counts'] or 'none'}`",
            f"- Metadata parse issues: `{f['metadata_issues'] or 'none'}`",
            f"- Rows with source / destination IP: {f['ip_available_rows']['src_ip']} / "
            f"{f['ip_available_rows']['dst_ip']}",
            f"- Time range (UTC): {f['time_range_utc'] or 'no timestamps in this file'}",
            "",
            "Label distribution after normalisation:",
            "",
            "| Class | Rows |",
            "|---|---|",
            *[f"| {k} | {v} |" for k, v in f["label_distribution"].items()],
            "",
            f"Raw `attack_cat` values (top {TOP_VALUES}): "
            f"`{f['raw_value_counts'][CATEGORY_COLUMN]}`",
            "",
            *[
                f"Raw `{c}` values: {f['distinct_raw_values'][c]} distinct; top: "
                f"`{f['raw_value_counts'][c]}`"
                for c in CATEGORICAL_FEATURES
            ],
            "",
        ]
    return "\n".join(out)


def write_profile(data_dir: Path, reports_dir: Path) -> Path:
    profile = profile_dataset(data_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "data_profile.json").write_text(
        json.dumps(profile, indent=2) + "\n", encoding="utf-8"
    )
    target = reports_dir / "data_profile.md"
    target.write_text(render_profile_markdown(profile), encoding="utf-8")
    return target
