"""Helpers for integration tests. All data here is SYNTHETIC."""

import io
from typing import Any

import pandas as pd
from sentinel_ml.testing import make_partitioned_frame
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.model_version import ModelVersion


def synthetic_csv(rows: int = 200, seed: int = 11, bad_rows: int = 0) -> bytes:
    frame = make_partitioned_frame(max(rows, 40), seed=seed).head(rows).astype(str)
    for i in range(bad_rows):
        frame.loc[i, "sbytes"] = "not-a-number"
    return frame.to_csv(index=False).encode("utf-8")


def synthetic_frame(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)


def make_alert(db: Session, model: ModelVersion, **overrides: Any) -> Alert:
    values: dict[str, Any] = {
        "source": "dataset",
        "model_version_id": model.id,
        "src_ip": "10.10.0.23",
        "dst_ip": "10.10.0.5",
        "src_port": 51544,
        "dst_port": 80,
        "protocol": "tcp",
        "service": "http",
        "predicted_category": "Reconnaissance",
        "attack_score": 0.91,
        "severity": "medium",
        "status": "new",
        "evidence": {"note": "synthetic test alert"},
    }
    values.update(overrides)
    alert = Alert(**values)
    db.add(alert)
    db.commit()
    return alert
