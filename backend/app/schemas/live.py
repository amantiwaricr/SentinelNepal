"""Schemas for collector ingest, collectors, and live monitoring status."""

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, IPvAnyAddress, field_validator
from sentinel_ml.schema import ALL_FEATURES

from app.schemas.common import OrmModel, StrictModel
from app.schemas.ops import ModelBrief

CollectorMode = Literal["observation", "inference"]
MAX_BATCH = 500
_FEATURES = frozenset(ALL_FEATURES)
_MAX_TIMESTAMP = 4_102_444_800  # 2100-01-01: rejects absurd clock values


class FlowRecordIn(StrictModel):
    """One flow from a collector. Validated per record: a bad record is counted and
    skipped without rejecting the rest of its batch."""

    flow_id: str = Field(min_length=1, max_length=200, pattern=r"^[\x20-\x7e]+$")
    feature_source: Literal["tshark", "dataset_csv"]
    start_time: float | None = Field(default=None, gt=0, lt=_MAX_TIMESTAMP)
    last_time: float | None = Field(default=None, gt=0, lt=_MAX_TIMESTAMP)
    src_ip: IPvAnyAddress | None = None
    dst_ip: IPvAnyAddress | None = None
    src_port: int | None = Field(default=None, ge=0, le=65535)
    dst_port: int | None = Field(default=None, ge=0, le=65535)
    features: dict[str, float | int | str | None] = Field(max_length=len(ALL_FEATURES))

    @field_validator("features")
    @classmethod
    def _known_finite_features(
        cls, value: dict[str, float | int | str | None]
    ) -> dict[str, float | int | str | None]:
        unknown = set(value) - _FEATURES
        if unknown:
            raise ValueError(f"unknown features: {sorted(unknown)[:5]}")
        for name, item in value.items():
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError(f"{name}: not a finite number")
            if isinstance(item, str) and len(item) > 32:
                raise ValueError(f"{name}: text too long")
        return value


class IngestFlowsIn(StrictModel):
    source: Literal["live", "replay"]
    # Validated one by one (FlowRecordIn) so a malformed record does not sink its batch.
    records: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_BATCH)


class IngestFlowsOut(StrictModel):
    accepted: int
    rejected: int
    dropped: int
    mode: CollectorMode
    rejection_examples: list[str]


class HeartbeatIn(StrictModel):
    status: Literal["running", "degraded", "stopping"]
    stats: dict[str, int | float | str] = Field(default_factory=dict, max_length=30)
    last_error: str | None = Field(default=None, max_length=500)

    @field_validator("stats")
    @classmethod
    def _plain_stats(cls, value: dict[str, int | float | str]) -> dict[str, int | float | str]:
        for key, item in value.items():
            if len(key) > 40 or not key.replace("_", "").isalnum():
                raise ValueError("stat names must be short identifiers")
            if isinstance(item, str) and len(item) > 200:
                raise ValueError(f"{key}: text too long")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError(f"{key}: not a finite number")
        return value


class HeartbeatOut(StrictModel):
    mode: CollectorMode
    live_scoring: bool


class CollectorOut(OrmModel):
    id: int
    name: str
    mode: CollectorMode
    online: bool = False
    last_heartbeat_at: datetime | None
    records_received: int
    records_rejected: int
    records_dropped: int
    records_processed: int
    alerts_created: int
    last_error: str | None
    heartbeat_stats: dict[str, Any]
    created_at: datetime


class CollectorModeIn(StrictModel):
    mode: CollectorMode


class LiveApprovalIn(StrictModel):
    approved: bool


class LiveStatusOut(StrictModel):
    live_model_profile: str
    model: ModelBrief | None
    alert_threshold: float | None
    compatible: bool | None
    unavailable_features: list[str]
    approximate_features: list[str]
    approved: bool
    model_ready: bool
    reason: str
    collectors_total: int
    collectors_online: int
    collectors_scoring: int
    queue_batches: int


class RecentFlowOut(StrictModel):
    collector_id: int
    source: Literal["live", "replay"]
    observed_at: datetime | None
    src_ip: str | None
    src_port: int | None
    dst_ip: str | None
    dst_port: int | None
    proto: str | None
    service: str | None
    state: str | None
    dur: float | None
    spkts: float | None
    dpkts: float | None
    sbytes: float | None
    dbytes: float | None
    scored: bool
