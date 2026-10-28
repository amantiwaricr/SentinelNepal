import csv
from pathlib import Path

import pandas as pd
import pytest

from sentinel_ml.features.dataset import (
    DatasetError,
    data_origin,
    detect_schema,
    find_file,
    load_files,
    sha256_file,
)
from sentinel_ml.schema import FEATURES_DESCRIPTION_FILE, FULL_RECORD_COLUMNS, TRAIN_FILE
from sentinel_ml.testing import full_record_rows, write_synthetic_partitioned

# Raw names as they appear in the published description file (mixed case, a stray space).
RAW_DESCRIPTION_NAMES = [
    "srcip",
    "sport",
    "dstip",
    "dsport",
    "proto",
    "state",
    "dur",
    "sbytes",
    "dbytes",
    "sttl",
    "dttl",
    "sloss",
    "dloss",
    "service",
    "Sload",
    "Dload",
    "Spkts",
    "Dpkts",
    "swin",
    "dwin",
    "stcpb",
    "dtcpb",
    "smeansz",
    "dmeansz",
    "trans_depth",
    "res_bdy_len",
    "Sjit",
    "Djit",
    "Stime",
    "Ltime",
    "Sintpkt",
    "Dintpkt",
    "tcprtt",
    "synack",
    "ackdat",
    "is_sm_ips_ports",
    "ct_state_ttl",
    "ct_flw_http_mthd",
    "is_ftp_login",
    "ct_ftp_cmd",
    "ct_srv_src",
    "ct_srv_dst",
    "ct_dst_ltm",
    "ct_src_ ltm",
    "ct_src_dport_ltm",
    "ct_dst_sport_ltm",
    "ct_dst_src_ltm",
    "attack_cat",
    "Label",
]


def _write_full_records(directory: Path, with_description: bool) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "UNSW-NB15_1.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(full_record_rows())
    if with_description:
        pd.DataFrame(
            {"No.": range(1, 50), "Name": RAW_DESCRIPTION_NAMES, "Type ": "x", "Description": "y"}
        ).to_csv(directory / FEATURES_DESCRIPTION_FILE, index=False, encoding="latin-1")
    return path


def test_raw_description_names_normalise_to_expected_columns() -> None:
    from sentinel_ml.schema import normalize_column_name

    assert [normalize_column_name(n) for n in RAW_DESCRIPTION_NAMES] == list(FULL_RECORD_COLUMNS)


def test_detects_both_file_families(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path / "p", train_rows=60, test_rows=60)
    assert detect_schema(tmp_path / "p" / TRAIN_FILE) == "unsw_partitioned"
    assert detect_schema(_write_full_records(tmp_path / "f", False)) == "unsw_full"


def test_unrecognised_and_empty_files_are_rejected(tmp_path: Path) -> None:
    odd = tmp_path / "odd.csv"
    odd.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="unrecognised layout"):
        detect_schema(odd)
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(DatasetError, match="empty"):
        detect_schema(empty)


@pytest.mark.parametrize("with_description", [True, False])
def test_full_record_files_load_with_metadata(tmp_path: Path, with_description: bool) -> None:
    path = _write_full_records(tmp_path, with_description)
    dataset = load_files([path], data_dir=tmp_path)
    assert dataset.schema_kind == "unsw_full"
    assert dataset.labels.tolist() == ["Normal", "Fuzzers", "Backdoor", "Reconnaissance"]
    assert dataset.metadata["src_ip"].tolist() == ["10.0.0.1", "10.0.0.3", "10.0.0.5", None]
    assert dataset.metadata["src_port"].tolist() == [1390, 11, 33661, 80]
    assert dataset.metadata_issues["unparseable_src_ip"] == 1
    # The blank HTTP/FTP counters are kept as missing, to be imputed by the model pipeline.
    assert dataset.features["ct_flw_http_mthd"].isna().all()


def test_description_file_that_disagrees_is_rejected(tmp_path: Path) -> None:
    path = _write_full_records(tmp_path, with_description=True)
    description = pd.read_csv(tmp_path / FEATURES_DESCRIPTION_FILE)
    description.loc[0, "Name"] = "something_else"
    description.to_csv(tmp_path / FEATURES_DESCRIPTION_FILE, index=False)
    with pytest.raises(DatasetError, match="differ"):
        load_files([path], data_dir=tmp_path)


def test_missing_columns_in_file_are_reported_with_file_name(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path, train_rows=60, test_rows=60)
    path = tmp_path / TRAIN_FILE
    pd.read_csv(path).drop(columns=["dur"]).to_csv(path, index=False)
    with pytest.raises(DatasetError, match=r"UNSW_NB15_training-set.csv: Missing required"):
        load_files([path])


def test_header_only_file_is_rejected(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path, train_rows=60, test_rows=60)
    path = tmp_path / TRAIN_FILE
    pd.read_csv(path).head(0).to_csv(path, index=False)
    with pytest.raises(DatasetError, match="no data rows"):
        load_files([path])


def test_mixing_file_families_is_rejected(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path, train_rows=60, test_rows=60)
    full = _write_full_records(tmp_path / "full", False)
    with pytest.raises(DatasetError, match="mix"):
        load_files([tmp_path / TRAIN_FILE, full])


def test_chunked_loading_matches_single_pass(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path, train_rows=300, test_rows=60)
    whole = load_files([tmp_path / TRAIN_FILE])
    chunked = load_files([tmp_path / TRAIN_FILE], chunk_rows=7)
    pd.testing.assert_frame_equal(whole.features, chunked.features)
    assert whole.labels.tolist() == chunked.labels.tolist()


def test_sources_origin_and_lookup(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path, train_rows=60, test_rows=60)
    path = find_file(tmp_path, TRAIN_FILE.upper())
    dataset = load_files([path])
    assert dataset.origin == "synthetic" == data_origin(tmp_path)
    assert dataset.sources[0].sha256 == sha256_file(path)
    assert data_origin(tmp_path / "elsewhere") == "unsw-nb15"


def test_missing_file_and_directory_errors_point_to_instructions(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match=r"ml/data/README.md"):
        find_file(tmp_path, TRAIN_FILE)
    with pytest.raises(DatasetError, match="not found"):
        find_file(tmp_path / "missing", TRAIN_FILE)


def test_unlabelled_file_with_header_is_recognised(tmp_path: Path) -> None:
    write_synthetic_partitioned(tmp_path, train_rows=60, test_rows=60)
    path = tmp_path / "upload.csv"
    pd.read_csv(tmp_path / TRAIN_FILE).drop(columns=["label", "attack_cat"]).to_csv(
        path, index=False
    )
    assert detect_schema(path) == "unsw_partitioned"
