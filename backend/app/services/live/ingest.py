"""From ingested flow records to alerts: bounded queue, gate check, scoring, persistence.

The ingest endpoint only validates and enqueues, so a burst of traffic can never block the
API; the live worker thread takes batches off the queue and does the slow work.
"""

import hashlib
import logging
import queue
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utcnow
from app.models.alert import Alert
from app.models.collector import Collector
from app.services.alerts import alert_from_prediction, should_alert
from app.services.events import EventHub
from app.services.live.gate import live_gate
from app.services.ml_service import ModelUnavailableError, PredictorCache
from app.services.models import active_model

logger = logging.getLogger(__name__)

RECENT_FLOWS = 200
# Above this many new alerts in one batch, one summary event is published instead of one each.
MAX_ALERT_EVENTS_PER_BATCH = 20


@dataclass(frozen=True)
class FlowIn:
    flow_id: str
    feature_source: Literal["tshark", "dataset_csv"]
    start_time: float | None
    last_time: float | None
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    features: dict[str, Any]


@dataclass(frozen=True)
class IngestBatch:
    collector_id: int
    source: Literal["live", "replay"]
    records: list[FlowIn]
    received_at: datetime = field(default_factory=utcnow)


class IngestQueue:
    """Bounded: when full, offer() refuses the batch and the caller counts it as dropped."""

    def __init__(self, max_batches: int) -> None:
        self._queue: queue.Queue[IngestBatch] = queue.Queue(maxsize=max_batches)

    def offer(self, batch: IngestBatch) -> bool:
        try:
            self._queue.put_nowait(batch)
        except queue.Full:
            return False
        return True

    def take(self, timeout: float) -> IngestBatch | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def size(self) -> int:
        return self._queue.qsize()


class RecentFlows:
    """The latest flows seen, for the Live Monitoring page. In memory, per API process."""

    def __init__(self, size: int = RECENT_FLOWS) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=size)
        self._lock = threading.Lock()

    def add(self, items: list[dict[str, Any]]) -> None:
        with self._lock:
            self._items.extend(items)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._items))


@dataclass
class BatchResult:
    processed: int = 0
    rejected: int = 0
    alerts: list[Alert] = field(default_factory=list)
    scored: bool = False
    reason: str = ""


def _timestamp(value: float | None) -> datetime | None:
    return None if value is None else datetime.fromtimestamp(value, tz=UTC)


def _summary(record: FlowIn, collector_id: int, source: str, scored: bool) -> dict[str, Any]:
    f = record.features
    return {
        "collector_id": collector_id,
        "source": source,
        "observed_at": _timestamp(record.start_time),
        "src_ip": record.src_ip,
        "src_port": record.src_port,
        "dst_ip": record.dst_ip,
        "dst_port": record.dst_port,
        "proto": f.get("proto"),
        "service": f.get("service"),
        "state": f.get("state"),
        "dur": f.get("dur"),
        "spkts": f.get("spkts"),
        "dpkts": f.get("dpkts"),
        "sbytes": f.get("sbytes"),
        "dbytes": f.get("dbytes"),
        "scored": scored,
    }


def dedup_key(source: str, collector_id: int, flow_id: str) -> str:
    digest = hashlib.sha256(flow_id.encode("utf-8")).hexdigest()
    return f"{source}:{collector_id}:{digest}"


def process_batch(
    db: Session,
    settings: Settings,
    predictors: PredictorCache,
    batch: IngestBatch,
) -> BatchResult:
    """Score one batch if the gate allows it and store the resulting alerts."""
    result = BatchResult(processed=len(batch.records))
    collector = db.get(Collector, batch.collector_id)
    if collector is None:
        result.reason = "collector no longer exists"
        return result

    if batch.source == "replay":
        # Replayed records carry dataset feature values, so only an active model is needed.
        model = active_model(db, settings.live_model_profile)
        allowed = model is not None
        result.reason = "" if allowed else f"no active '{settings.live_model_profile}' model"
    else:
        gate = live_gate(db, settings)
        model = gate.model
        allowed = collector.mode == "inference" and gate.model_ready
        result.reason = (
            "" if allowed else "collector in observation mode" if gate.model_ready else gate.reason
        )

    error: str | None = None
    predictor = None
    if allowed and model is not None:
        try:
            predictor = predictors.get(model)
        except ModelUnavailableError as exc:
            error = result.reason = exc.message
    if predictor is not None and model is not None:
        result.scored = True
        predictions = predictor.predict_records([r.features for r in batch.records])
        result.rejected = len(predictions.rejected)
        candidates: dict[str, Alert] = {}
        for prediction in predictions.predictions:
            if not should_alert(prediction, model.alert_threshold):
                continue
            record = batch.records[prediction.index]
            key = dedup_key(batch.source, collector.id, record.flow_id)
            alert = alert_from_prediction(prediction, model, source=batch.source, dedup_key=key)
            alert.collector_id = collector.id
            alert.observed_at = _timestamp(record.start_time)
            alert.src_ip, alert.dst_ip = record.src_ip, record.dst_ip
            alert.src_port, alert.dst_port = record.src_port, record.dst_port
            alert.evidence = {
                **alert.evidence,
                "feature_source": record.feature_source,
                "flow_last_time": record.last_time,
            }
            candidates[key] = alert
        # Duplicate flows (a collector resending after a timeout) never create a second alert.
        existing = set(
            db.scalars(select(Alert.dedup_key).where(Alert.dedup_key.in_(list(candidates))))
        )
        result.alerts = [a for k, a in candidates.items() if k not in existing]
        db.add_all(result.alerts)

    db.execute(
        update(Collector)
        .where(Collector.id == collector.id)
        .values(
            records_processed=Collector.records_processed + result.processed - result.rejected,
            records_rejected=Collector.records_rejected + result.rejected,
            alerts_created=Collector.alerts_created + len(result.alerts),
            **({"last_error": error} if error else {}),
        )
    )
    db.commit()
    return result


def publish_batch_events(
    hub: EventHub, recent: RecentFlows, batch: IngestBatch, result: BatchResult
) -> None:
    recent.add(
        [_summary(r, batch.collector_id, batch.source, result.scored) for r in batch.records]
    )
    hub.publish(
        {
            "type": "flows.observed",
            "collector_id": batch.collector_id,
            "source": batch.source,
            "count": len(batch.records),
            "scored": result.scored,
        }
    )
    if len(result.alerts) > MAX_ALERT_EVENTS_PER_BATCH:
        hub.publish({"type": "alerts.created", "count": len(result.alerts), "source": batch.source})
        return
    for alert in result.alerts:
        hub.publish(
            {
                "type": "alert.created",
                "alert": {
                    "id": alert.id,
                    "source": alert.source,
                    "severity": alert.severity,
                    "predicted_category": alert.predicted_category,
                    "src_ip": None if alert.src_ip is None else str(alert.src_ip),
                },
            }
        )
