import math

import pandas as pd
import pytest

from sentinel_ml.features.cleaning import SchemaError, clean_frame
from sentinel_ml.schema import ALL_FEATURES, NUMERIC_FEATURES
from tests.synthetic import make_partitioned_frame


def _frame(rows: int = 3) -> pd.DataFrame:
    """SYNTHETIC rows as raw strings, like a CSV read."""
    return make_partitioned_frame(rows=max(rows, 40), seed=1).head(rows).astype(str)


def _clean(frame: pd.DataFrame, labels: bool = True):  # type: ignore[no-untyped-def]
    return clean_frame(frame, ALL_FEATURES, require_labels=labels)


def test_valid_rows_are_typed_and_ordered() -> None:
    result = _clean(_frame())
    assert list(result.features.columns) == list(ALL_FEATURES)
    assert all(result.features[c].dtype == "float64" for c in NUMERIC_FEATURES)
    assert not result.rejected


def test_missing_required_columns_raise() -> None:
    with pytest.raises(SchemaError, match="sbytes"):
        _clean(_frame().drop(columns=["sbytes"]))


def test_missing_label_columns_raise_only_when_labels_required() -> None:
    frame = _frame().drop(columns=["label", "attack_cat"])
    with pytest.raises(SchemaError, match="label"):
        _clean(frame)
    assert len(_clean(frame, labels=False).features) == 3


def test_extra_columns_are_ignored() -> None:
    result = _clean(_frame().assign(unexpected_column="x"))
    assert "unexpected_column" not in result.features.columns
    assert not result.rejected


@pytest.mark.parametrize("bad", ["abc", "inf", "-inf", "1e400", "1,5"])
def test_invalid_numeric_values_reject_the_row(bad: str) -> None:
    frame = _frame()
    frame.loc[1, "sbytes"] = bad
    result = _clean(frame)
    assert result.rejected == {1: ["invalid_value:sbytes"]}
    assert len(result.features) == 2


def test_python_booleans_are_not_accepted_as_numbers() -> None:
    frame = _frame().astype(object)
    frame.loc[0, "dur"] = True
    assert _clean(frame).rejected == {0: ["invalid_value:dur"]}


def test_blank_required_value_rejects_but_blank_nullable_is_kept() -> None:
    frame = _frame()
    frame.loc[0, "dur"] = " "
    frame.loc[1, "ct_flw_http_mthd"] = ""
    result = _clean(frame)
    assert result.rejected == {0: ["missing_value:dur"]}
    assert result.features["ct_flw_http_mthd"].isna().sum() == 1


def test_categories_are_normalised_and_long_values_rejected() -> None:
    frame = _frame()
    frame.loc[0, "proto"] = "  TCP "
    frame.loc[1, "service"] = "x" * 33
    result = _clean(frame)
    assert result.features.loc[0, "proto"] == "tcp"
    assert result.rejected == {1: ["invalid_value:service"]}


def test_non_string_category_rejected() -> None:
    frame = _frame().astype(object)
    frame.loc[0, "state"] = 7
    assert _clean(frame).rejected == {0: ["invalid_value:state"]}


@pytest.mark.parametrize(
    ("category", "label", "expected"),
    [
        (" Fuzzers ", "1", "Fuzzers"),
        ("Backdoors", "1", "Backdoor"),
        ("reconnaissance", "1", "Reconnaissance"),
        ("", "0", "Normal"),
        ("Normal", "0", "Normal"),
    ],
)
def test_label_normalisation(category: str, label: str, expected: str) -> None:
    frame = _frame(1)
    frame.loc[0, ["attack_cat", "label"]] = [category, label]
    result = _clean(frame)
    assert result.labels is not None
    assert result.labels.tolist() == [expected]


@pytest.mark.parametrize(
    ("category", "label", "reason"),
    [
        ("", "1", "unknown_attack_category"),
        ("Ransomware", "1", "unknown_attack_category"),
        ("DoS", "0", "label_category_inconsistent"),
        ("Normal", "1", "label_category_inconsistent"),
        ("DoS", "2", "invalid_label"),
        ("DoS", "yes", "invalid_label"),
    ],
)
def test_bad_labels_reject_the_row(category: str, label: str, reason: str) -> None:
    frame = _frame(1)
    frame.loc[0, ["attack_cat", "label"]] = [category, label]
    assert _clean(frame).rejected == {0: [reason]}


def test_metadata_is_parsed_but_never_rejects_rows() -> None:
    frame = _frame(4).assign(
        srcip=["10.0.0.1", "not-an-ip", "2001:DB8::1", ""],
        sport=["1390", "0x000b", "-", "70000"],
        stime=["1421927414", "", "x", "1421927414"],
    )
    result = _clean(frame)
    assert not result.rejected
    metadata = result.metadata
    assert metadata["src_ip"].tolist() == ["10.0.0.1", None, "2001:db8::1", None]
    assert metadata["src_port"].tolist()[:2] == [1390, 11]
    assert metadata["src_port"].isna().tolist()[2:] == [True, True]
    assert str(metadata["start_time"][0]) == "2015-01-22 11:50:14+00:00"
    assert result.metadata_issues == {
        "unparseable_src_ip": 1,
        "unparseable_src_port": 2,
        "unparseable_start_time": 1,
    }


def test_empty_frame_gives_empty_result() -> None:
    result = _clean(_frame().iloc[0:0])
    assert result.features.empty
    assert not result.rejected


def test_multiple_problems_are_all_reported() -> None:
    frame = _frame(1)
    frame.loc[0, ["dur", "proto", "label"]] = ["", "", "9"]
    reasons = _clean(frame).rejected[0]
    assert set(reasons) == {"missing_value:dur", "missing_value:proto", "invalid_label"}
    assert not math.isnan(len(reasons))
