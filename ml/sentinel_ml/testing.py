"""SYNTHETIC test data in the UNSW-NB15 file layouts — for automated tests only.

Shared by the ml/ and backend/ test suites so neither copies the other's helpers.

Values are random with class-dependent shifts so that models can learn *something*; they
do not resemble real traffic. Directories written here contain the synthetic marker file,
so every report produced from them is labelled synthetic.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sentinel_ml.schema import (
    CLASS_LABELS,
    FULL_RECORD_COLUMNS,
    NORMAL,
    PARTITIONED_COLUMNS,
    SYNTHETIC_MARKER_FILE,
    TEST_FILE,
    TRAIN_FILE,
)

CLASS_WEIGHTS = {
    NORMAL: 0.40,
    "Generic": 0.14,
    "Exploits": 0.14,
    "Fuzzers": 0.10,
    "DoS": 0.06,
    "Reconnaissance": 0.06,
    "Analysis": 0.025,
    "Backdoor": 0.025,
    "Shellcode": 0.025,
    "Worms": 0.025,
}
PROTOS = ["tcp", "udp", "arp", "ospf", "unas"]
SERVICES = ["-", "http", "dns", "ftp", "smtp", "ftp-data"]
STATES = ["FIN", "INT", "CON", "REQ", "RST"]


def make_partitioned_frame(rows: int, seed: int) -> pd.DataFrame:
    """A frame with the partitioned-file header and class-dependent synthetic values."""
    rng = np.random.default_rng(seed)
    labels = rng.choice(list(CLASS_WEIGHTS), size=rows, p=list(CLASS_WEIGHTS.values()))
    # Guarantee every class appears often enough for a stratified split.
    labels[: len(CLASS_LABELS) * 4] = np.repeat(CLASS_LABELS, 4)
    index = np.array([CLASS_LABELS.index(label) for label in labels])

    frame = pd.DataFrame({"id": np.arange(1, rows + 1)})
    for column in PARTITIONED_COLUMNS:
        if column in ("id", "attack_cat", "label", "proto", "service", "state"):
            continue
        base = rng.lognormal(mean=1.0, sigma=1.0, size=rows)
        frame[column] = np.round(base * (1 + index * 0.6) + rng.normal(0, 0.3, rows), 6)
    for column in ("sttl", "dttl", "spkts", "dpkts", "ct_srv_src", "ct_dst_ltm", "trans_depth"):
        frame[column] = (frame[column].abs() * 3).round().astype(int)
    for column in ("is_ftp_login", "is_sm_ips_ports"):
        frame[column] = (rng.random(rows) < 0.05).astype(int)
    frame["proto"] = [PROTOS[(i + rng.integers(0, 2)) % len(PROTOS)] for i in index]
    frame["service"] = [SERVICES[(i * 2 + rng.integers(0, 2)) % len(SERVICES)] for i in index]
    frame["state"] = [STATES[i % len(STATES)] for i in index]
    frame["attack_cat"] = labels
    frame["label"] = (labels != NORMAL).astype(int)
    return frame[list(PARTITIONED_COLUMNS)]


def write_synthetic_partitioned(
    data_dir: Path, train_rows: int = 1500, test_rows: int = 600, seed: int = 7
) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / SYNTHETIC_MARKER_FILE).write_text(
        "Synthetic test data. Not UNSW-NB15.\n", encoding="utf-8"
    )
    make_partitioned_frame(train_rows, seed).to_csv(data_dir / TRAIN_FILE, index=False)
    test = make_partitioned_frame(test_rows, seed + 1)
    # Copy a few training rows into the test file to exercise the overlap report.
    train = pd.read_csv(data_dir / TRAIN_FILE)
    test.iloc[:5] = train.iloc[:5].to_numpy()
    test.to_csv(data_dir / TEST_FILE, index=False)
    return data_dir


def full_record_rows() -> list[list[str]]:
    """Header-less full-record rows with the quirks of the published files."""
    base = {name: "1" for name in FULL_RECORD_COLUMNS}
    base.update(
        proto="tcp",
        state="FIN",
        service="-",
        start_time="1421927414",
        last_time="1421927416",
        ct_flw_http_mthd="",
        is_ftp_login="",
    )

    def row(**overrides: str) -> list[str]:
        values = {**base, **overrides}
        return [values[name] for name in FULL_RECORD_COLUMNS]

    return [
        row(
            src_ip="10.0.0.1",
            src_port="1390",
            dst_ip="10.0.0.2",
            dst_port="53",
            attack_cat="",
            label="0",
        ),
        row(
            src_ip="10.0.0.3",
            src_port="0x000b",
            dst_ip="10.0.0.4",
            dst_port="-",
            attack_cat=" Fuzzers ",
            label="1",
        ),
        row(
            src_ip="10.0.0.5",
            src_port="33661",
            dst_ip="10.0.0.6",
            dst_port="80",
            attack_cat="Backdoors",
            label="1",
        ),
        row(
            src_ip="not-an-ip",
            src_port="80",
            dst_ip="2001:db8::1",
            dst_port="443",
            attack_cat=" Reconnaissance",
            label="1",
        ),
    ]
