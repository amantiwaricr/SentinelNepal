"""Validation and type coercion shared by training, evaluation, profiling, and inference.

Every record goes through :func:`clean_frame`. Invalid values reject the record with a stated
reason; nothing is silently replaced, except features listed in ``NULLABLE_FEATURES``, which
the saved pipeline imputes (and the predictor reports as imputed).
"""

from __future__ import annotations

import ipaddress
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from sentinel_ml.schema import (
    CATEGORICAL_FEATURES,
    CATEGORY_ALIASES,
    CATEGORY_COLUMN,
    LABEL_COLUMN,
    METADATA_COLUMNS,
    NORMAL,
    NULLABLE_FEATURES,
    normalize_column_name,
)

MAX_CATEGORY_LENGTH = 32


class SchemaError(ValueError):
    """The input as a whole cannot be used (e.g. required columns are missing)."""


@dataclass
class CleanResult:
    features: pd.DataFrame  # valid rows only, required features in the requested order
    labels: pd.Series | None  # canonical class labels for valid rows, if requested
    metadata: pd.DataFrame  # investigation metadata for valid rows (may be all-null)
    rejected: dict[int, list[str]] = field(default_factory=dict)  # input position -> reasons
    metadata_issues: Counter[str] = field(default_factory=Counter)

    @property
    def rejection_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for reasons in self.rejected.values():
            counts.update(reasons)
        return counts


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(columns=lambda c: normalize_column_name(str(c)))
    duplicated = renamed.columns[renamed.columns.duplicated()].tolist()
    if duplicated:
        raise SchemaError(f"Duplicate columns after normalising names: {sorted(set(duplicated))}")
    return renamed


def _is_blank(series: pd.Series) -> pd.Series:
    as_text = series.astype("string").str.strip()
    return series.isna() | (as_text == "")


def _coerce_numeric(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (values, missing_mask, invalid_mask). Booleans count as invalid."""
    blank = _is_blank(series)
    is_bool = series.map(lambda v: isinstance(v, bool | np.bool_))
    values = pd.to_numeric(series.where(~is_bool), errors="coerce").astype("float64")
    invalid = (~blank & values.isna()) | is_bool | np.isinf(values)
    values = values.where(~invalid)
    return values, blank & ~is_bool, invalid


def _clean_category(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    blank = _is_blank(series)
    is_text = series.map(lambda v: isinstance(v, str))
    text = series.astype("string").str.strip().str.lower()
    invalid = ~blank & (~is_text | (text.str.len() > MAX_CATEGORY_LENGTH))
    values = text.where(~blank & ~invalid).astype(object)
    return values, blank, invalid


def _clean_labels(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return (canonical labels, reason per row or None)."""
    label_values, label_blank, label_invalid = _coerce_numeric(frame[LABEL_COLUMN])
    category_raw = frame[CATEGORY_COLUMN].astype("string").str.strip().str.lower()
    category_raw = category_raw.where(~_is_blank(frame[CATEGORY_COLUMN]))

    canonical = category_raw.map(lambda v: CATEGORY_ALIASES.get(v) if isinstance(v, str) else None)
    # Normal traffic has a blank attack_cat in the full-record files.
    canonical = canonical.where(~(category_raw.isna() & (label_values == 0)), NORMAL)

    reasons = pd.Series([None] * len(frame), index=frame.index, dtype=object)
    bad_label = label_blank | label_invalid | ~label_values.isin([0, 1])
    reasons[bad_label] = "invalid_label"
    unknown = ~bad_label & canonical.isna()
    reasons[unknown] = "unknown_attack_category"
    inconsistent = ~bad_label & ~unknown & ((canonical == NORMAL) != (label_values == 0))
    reasons[inconsistent] = "label_category_inconsistent"
    return canonical.astype(object), reasons


def _parse_ip(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _parse_port(value: object) -> float:
    # Full-record files contain decimal ports, hexadecimal ones such as "0x000b", and "-".
    if isinstance(value, int | float) and not isinstance(value, bool):
        number = int(value) if np.isfinite(value) else -1
    elif isinstance(value, str):
        text = value.strip().lower()
        try:
            number = int(text, 16) if text.startswith("0x") else int(text)
        except ValueError:
            return np.nan
    else:
        return np.nan
    return float(number) if 0 <= number <= 65535 else np.nan


def _clean_metadata(frame: pd.DataFrame, issues: Counter[str]) -> pd.DataFrame:
    metadata = pd.DataFrame(index=frame.index)
    for column in METADATA_COLUMNS:
        if column not in frame.columns:
            metadata[column] = None
            continue
        raw = frame[column]
        present = ~_is_blank(raw)
        if column in ("src_ip", "dst_ip"):
            # Explicit object dtype keeps None (JSON null) rather than letting pandas turn
            # missing addresses into NaN.
            parsed = pd.Series([_parse_ip(v) for v in raw], index=frame.index, dtype=object)
            metadata[column] = parsed
        elif column in ("src_port", "dst_port"):
            parsed = raw.map(_parse_port).astype("Int64")
            metadata[column] = parsed
        else:
            seconds = pd.to_numeric(raw, errors="coerce")
            parsed = pd.to_datetime(seconds, unit="s", utc=True, errors="coerce")
            metadata[column] = parsed
        bad = int((present & pd.Series(parsed, index=frame.index).isna()).sum())
        if bad:
            issues[f"unparseable_{column}"] += bad
    return metadata


def clean_frame(
    frame: pd.DataFrame,
    required_features: Iterable[str],
    *,
    require_labels: bool,
    nullable_features: frozenset[str] = NULLABLE_FEATURES,
) -> CleanResult:
    """Validate and coerce raw records. ``frame`` may contain raw (un-normalised) columns."""
    required = list(required_features)
    normalized = normalize_columns(frame).reset_index(drop=True)

    expected = [*required, *([LABEL_COLUMN, CATEGORY_COLUMN] if require_labels else [])]
    missing = [column for column in expected if column not in normalized.columns]
    if missing:
        raise SchemaError(f"Missing required columns: {missing}")

    reasons: list[list[str]] = [[] for _ in range(len(normalized))]

    def add(mask: pd.Series, reason: str) -> None:
        for position in np.flatnonzero(mask.to_numpy()):
            reasons[position].append(reason)

    features = pd.DataFrame(index=normalized.index)
    for column in required:
        if column in CATEGORICAL_FEATURES:
            values, blank, invalid = _clean_category(normalized[column])
        else:
            values, blank, invalid = _coerce_numeric(normalized[column])
        features[column] = values
        add(invalid, f"invalid_value:{column}")
        if column not in nullable_features:
            add(blank, f"missing_value:{column}")

    labels: pd.Series | None = None
    if require_labels:
        labels, label_reasons = _clean_labels(normalized)
        for position in np.flatnonzero(label_reasons.notna().to_numpy()):
            reasons[position].append(str(label_reasons.iloc[position]))

    metadata_issues: Counter[str] = Counter()
    metadata = _clean_metadata(normalized, metadata_issues)

    valid = np.array([not r for r in reasons], dtype=bool)
    rejected = {position: r for position, r in enumerate(reasons) if r}
    return CleanResult(
        features=features[valid].reset_index(drop=True),
        labels=labels[valid].reset_index(drop=True) if labels is not None else None,
        metadata=metadata[valid].reset_index(drop=True),
        rejected=rejected,
        metadata_issues=metadata_issues,
    )
