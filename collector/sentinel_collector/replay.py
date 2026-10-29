"""Replays a CSV of flows through the live pipeline (source "replay").

Accepts UNSW-NB15 files (partitioned with header, or full-record without header) and CSVs
written by ``sentinel-ml pcap-features``. Values go through the same validation as dataset
analysis; invalid rows are skipped and counted. Label columns are ignored.
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import Any

from sentinel_ml.features.cleaning import clean_frame
from sentinel_ml.features.dataset import detect_schema, iter_raw_chunks
from sentinel_ml.schema import ALL_FEATURES, CATEGORICAL_FEATURES

from sentinel_collector.sender import Sender

logger = logging.getLogger(__name__)

# ct_state_ttl is not used by the live model and not written by pcap-features.
REPLAY_FEATURES = tuple(f for f in ALL_FEATURES if f != "ct_state_ttl")


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _port(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and 0 <= number <= 65535 else None


def _text(value: Any) -> str | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)


def replay_csv(
    path: Path, sender: Sender, *, rate: float = 0.0, limit: int | None = None
) -> dict[str, int]:
    """Send rows as replayed flows. ``rate`` > 0 limits rows per second."""
    kind = detect_schema(path)
    sent = rejected = 0
    started = time.monotonic()
    for chunk in iter_raw_chunks(path, kind, None, chunk_rows=1000):
        cleaned = clean_frame(chunk, REPLAY_FEATURES, require_labels=False)
        rejected += len(cleaned.rejected)
        records = []
        for (index, row), (_, meta) in zip(
            cleaned.features.iterrows(), cleaned.metadata.iterrows(), strict=True
        ):
            features = {
                name: (str(row[name]) if name in CATEGORICAL_FEATURES else float(row[name]))
                for name in REPLAY_FEATURES
                if row[name] is not None
                and not (isinstance(row[name], float) and math.isnan(row[name]))
            }
            records.append(
                {
                    "flow_id": f"{path.name}:{index}",
                    "feature_source": "dataset_csv",
                    "start_time": _number(meta.get("start_time")),
                    "last_time": _number(meta.get("last_time")),
                    "src_ip": _text(meta.get("src_ip")),
                    "dst_ip": _text(meta.get("dst_ip")),
                    "src_port": _port(meta.get("src_port")),
                    "dst_port": _port(meta.get("dst_port")),
                    "features": features,
                }
            )
            if limit is not None and sent + len(records) >= limit:
                break
        sender.enqueue(records)
        sender.flush()
        sent += len(records)
        if rate > 0:
            ahead = sent / rate - (time.monotonic() - started)
            if ahead > 0:
                time.sleep(ahead)
        if limit is not None and sent >= limit:
            break
    deadline = time.monotonic() + 60
    while sender.buffer and not sender.flush() and time.monotonic() < deadline:
        time.sleep(1)
    return {
        "rows_read": sent,
        "rows_rejected_locally": rejected,
        "unsent": len(sender.buffer),
        "accepted_by_api": sender.stats.sent,
    }
