from pathlib import Path

import pandas as pd

from sentinel_ml.features.profile import profile_dataset
from sentinel_ml.schema import TRAIN_FILE
from tests.synthetic import write_synthetic_partitioned


def test_profile_reports_real_file_properties(tmp_path: Path) -> None:
    data = write_synthetic_partitioned(tmp_path, train_rows=200, test_rows=80)
    frame = pd.read_csv(data / TRAIN_FILE, dtype=str, keep_default_na=False)
    frame.loc[0, "attack_cat"] = " Fuzzers "
    frame.loc[0, "label"] = "1"
    frame.loc[1, "sbytes"] = "oops"
    frame.loc[2, "ct_flw_http_mthd"] = ""
    frame = pd.concat([frame, frame.iloc[[10]]])
    frame.to_csv(data / TRAIN_FILE, index=False)

    profile = profile_dataset(data)
    train = next(f for f in profile["files"] if f["file"] == TRAIN_FILE)
    assert profile["data_origin"] == "synthetic"
    assert train["rows"] == 201
    assert train["missing_expected_columns"] == [] and train["unexpected_columns"] == []
    assert train["column_types"]["sbytes"] == "text"  # one non-numeric value makes it text
    assert train["non_numeric_values"]["sbytes"] == 1
    assert train["blank_values"] == {"ct_flw_http_mthd": 1}
    assert "' Fuzzers '" in train["raw_value_counts"]["attack_cat"]
    assert train["rejection_counts"] == {"invalid_value:sbytes": 1}
    assert train["duplicate_rows"] == 1
    assert train["ip_available_rows"] == {"src_ip": 0, "dst_ip": 0}
    # Test rows 0-4 copy training rows 0-4; rows 0-2 were altered above, so 2 still match.
    assert profile["distinct_test_rows_also_in_train"] == 2
