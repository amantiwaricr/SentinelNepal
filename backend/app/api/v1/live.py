"""Collector ingest (bearer token) and live monitoring status (signed-in users)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy import select, update

from app.api.deps import (
    AdminUser,
    AnalystUser,
    AppSettings,
    Audit,
    DbSession,
    client_ip,
    request_id,
)
from app.core.errors import AppError
from app.models.collector import Collector
from app.schemas.live import (
    CollectorModeIn,
    CollectorOut,
    FlowRecordIn,
    HeartbeatIn,
    HeartbeatOut,
    IngestFlowsIn,
    IngestFlowsOut,
    LiveStatusOut,
    RecentFlowOut,
)
from app.schemas.ops import ModelBrief
from app.services import audit
from app.services.audit import AuditContext
from app.services.live import collectors
from app.services.live.gate import live_gate
from app.services.live.ingest import FlowIn, IngestBatch, IngestQueue, RecentFlows

ingest_router = APIRouter(prefix="/ingest", tags=["ingest"])
router = APIRouter(tags=["live"])


def authenticated_collector(request: Request, db: DbSession) -> Collector:
    """Collectors authenticate with ``Authorization: Bearer <token>``. Failed attempts are
    rate limited per address and audited (up to the limit, so they cannot flood the log)."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else None
    collector = collectors.authenticate_collector(db, token)
    if collector is not None:
        return collector
    ip = client_ip(request)
    limiter = request.app.state.ingest_failure_limiter
    if not limiter.allow(f"ingest:{ip}"):
        raise AppError("rate_limited", "Too many failed collector authentications", 429)
    audit.record(
        db,
        AuditContext.anonymous(ip, request_id(request)),
        "collector.auth",
        outcome="denied",
        details={"reason": "missing token" if not token else "unknown token"},
    )
    db.commit()
    raise AppError("unauthenticated", "Invalid collector token", 401)


IngestCollector = Annotated[Collector, Depends(authenticated_collector)]


def _to_flow(record: FlowRecordIn) -> FlowIn:
    return FlowIn(
        flow_id=record.flow_id,
        feature_source=record.feature_source,
        start_time=record.start_time,
        last_time=record.last_time,
        src_ip=None if record.src_ip is None else str(record.src_ip),
        dst_ip=None if record.dst_ip is None else str(record.dst_ip),
        src_port=record.src_port,
        dst_port=record.dst_port,
        features=record.features,
    )


@ingest_router.post("/flows", response_model=IngestFlowsOut, status_code=202)
def ingest_flows(
    body: IngestFlowsIn, request: Request, collector: IngestCollector, db: DbSession
) -> IngestFlowsOut:
    """Validate a batch and queue it for scoring. Never waits for the model."""
    valid: list[FlowIn] = []
    examples: list[str] = []
    for position, raw in enumerate(body.records):
        try:
            valid.append(_to_flow(FlowRecordIn.model_validate(raw)))
        except ValidationError as exc:
            if len(examples) < 3:
                first = exc.errors()[0]
                field = ".".join(str(p) for p in first["loc"])
                examples.append(f"record {position}: {field}: {first['msg']}"[:200])
    rejected = len(body.records) - len(valid)
    dropped = 0
    if valid:
        queue: IngestQueue = request.app.state.ingest_queue
        if not queue.offer(IngestBatch(collector.id, body.source, valid)):
            dropped = len(valid)  # backpressure: refuse rather than block the API
    db.execute(
        update(Collector)
        .where(Collector.id == collector.id)
        .values(
            records_received=Collector.records_received + len(body.records),
            records_rejected=Collector.records_rejected + rejected,
            records_dropped=Collector.records_dropped + dropped,
        )
    )
    db.commit()
    return IngestFlowsOut(
        accepted=len(valid) - dropped,
        rejected=rejected,
        dropped=dropped,
        mode=collector.mode,
        rejection_examples=examples,
    )


@ingest_router.post("/heartbeat", response_model=HeartbeatOut)
def heartbeat(
    body: HeartbeatIn, collector: IngestCollector, db: DbSession, settings: AppSettings
) -> HeartbeatOut:
    collectors.record_heartbeat(
        db, collector, body.stats | {"status": body.status}, body.last_error
    )
    scoring = collector.mode == "inference" and live_gate(db, settings).model_ready
    return HeartbeatOut(mode=collector.mode, live_scoring=scoring)


def _collector_out(collector: Collector, settings: AppSettings) -> CollectorOut:
    out = CollectorOut.model_validate(collector)
    return out.model_copy(update={"online": collectors.is_online(collector, settings)})


@router.get("/collectors", response_model=list[CollectorOut])
def list_collectors(_: AnalystUser, db: DbSession, settings: AppSettings) -> list[CollectorOut]:
    rows = db.scalars(select(Collector).order_by(Collector.name)).all()
    return [_collector_out(c, settings) for c in rows]


@router.patch("/collectors/{collector_id}", response_model=CollectorOut)
def set_collector_mode(
    collector_id: int,
    body: CollectorModeIn,
    _: AdminUser,
    ctx: Audit,
    db: DbSession,
    settings: AppSettings,
) -> CollectorOut:
    """Switch between observation and inference (inference only through the gate)."""
    collector = collectors.set_mode(db, settings, ctx, collector_id, body.mode)
    return _collector_out(collector, settings)


@router.get("/live/status", response_model=LiveStatusOut)
def live_status(
    request: Request, _: AnalystUser, db: DbSession, settings: AppSettings
) -> LiveStatusOut:
    gate = live_gate(db, settings)
    rows = db.scalars(select(Collector)).all()
    online = [c for c in rows if collectors.is_online(c, settings)]
    report = gate.compatibility
    return LiveStatusOut(
        live_model_profile=settings.live_model_profile,
        model=None if gate.model is None else ModelBrief.model_validate(gate.model),
        alert_threshold=None if gate.model is None else gate.model.alert_threshold,
        compatible=None if report is None else report.compatible,
        unavailable_features=[] if report is None else report.unavailable,
        approximate_features=[] if report is None else report.approximate,
        approved=gate.approved,
        model_ready=gate.model_ready,
        reason=gate.reason,
        collectors_total=len(rows),
        collectors_online=len(online),
        collectors_scoring=sum(1 for c in rows if c.mode == "inference") if gate.model_ready else 0,
        queue_batches=request.app.state.ingest_queue.size,
    )


@router.get("/live/flows", response_model=list[RecentFlowOut])
def recent_flows(request: Request, _: AnalystUser) -> list[RecentFlowOut]:
    """The latest flows received (kept in memory, newest first); for observation."""
    recent: RecentFlows = request.app.state.recent_flows
    return [RecentFlowOut.model_validate(item) for item in recent.snapshot()]
