"""Write TShark-built flows as a CSV in the partitioned UNSW-NB15 layout.

The output has the dataset's feature names as its header (plus the connection metadata), so
it can be inspected in a spreadsheet, uploaded on the Dataset Analysis page, or replayed
through the live pipeline. It contains no packet payloads.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sentinel_ml.live.pcap import ReadStats, pcap_to_records
from sentinel_ml.schema import ALL_FEATURES

METADATA = ("src_ip", "src_port", "dst_ip", "dst_port", "start_time", "last_time")


def write_flows_csv(
    capture: Path, output: Path, *, tshark: str = "tshark"
) -> tuple[int, ReadStats]:
    records, stats = pcap_to_records(capture, tshark=tshark)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        columns = [f for f in ALL_FEATURES if f != "ct_state_ttl"]
        writer.writerow([*METADATA, *columns])
        for record in records:
            features = record["features"]
            writer.writerow(
                [*(record[m] if record[m] is not None else "" for m in METADATA)]
                + [features[c] for c in columns]
            )
    return len(records), stats
