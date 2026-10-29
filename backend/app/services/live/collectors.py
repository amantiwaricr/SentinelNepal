"""Collectors: creation (token shown once), authentication, heartbeats, mode changes."""

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hash_token, new_session_token
from app.core.time import utcnow
from app.models.collector import Collector
from app.services import audit
from app.services.audit import AuditContext
from app.services.live.gate import live_gate

MAX_ERROR_LENGTH = 500


COLLECTOR_NAME = re.compile(r"^[A-Za-z0-9._-]{3,64}$")


def create_collector(db: Session, ctx: AuditContext, name: str) -> tuple[Collector, str]:
    """Create a collector in observation mode. Returns it and its token (shown only once)."""
    if not COLLECTOR_NAME.match(name):
        raise AppError("invalid_name", "Use 3-64 letters, digits, dots, dashes or underscores", 422)
    token, token_hash = new_session_token()
    collector = Collector(name=name, token_hash=token_hash, mode="observation")
    db.add(collector)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("conflict", f"A collector named {name!r} already exists", 409) from None
    audit.record(
        db,
        ctx,
        "collector.created",
        target_type="collector",
        target_id=collector.id,
        details={"name": name},
    )
    db.commit()
    return collector, token


def rotate_token(db: Session, ctx: AuditContext, collector_id: int) -> str:
    collector = get_collector(db, collector_id)
    token, collector.token_hash = new_session_token()
    audit.record(
        db, ctx, "collector.token_rotated", target_type="collector", target_id=collector.id
    )
    db.commit()
    return token


def get_collector(db: Session, collector_id: int) -> Collector:
    collector = db.get(Collector, collector_id)
    if collector is None:
        raise AppError("not_found", "Collector not found", 404)
    return collector


def authenticate_collector(db: Session, token: str | None) -> Collector | None:
    """The collector owning this bearer token, or None. Only the hash is stored."""
    if not token or len(token) > 128:
        return None
    return db.scalar(select(Collector).where(Collector.token_hash == hash_token(token)))


def is_online(collector: Collector, settings: Settings, now: datetime | None = None) -> bool:
    """Online = a heartbeat within the offline threshold, unless the last one said the
    collector was shutting down (then it shows offline at once)."""
    if collector.last_heartbeat_at is None or collector.heartbeat_stats.get("status") == "stopping":
        return False
    now = now or utcnow()
    return now - collector.last_heartbeat_at <= timedelta(
        seconds=settings.collector_offline_seconds
    )


def record_heartbeat(
    db: Session, collector: Collector, stats: dict[str, Any], last_error: str | None
) -> None:
    collector.last_heartbeat_at = utcnow()
    collector.heartbeat_stats = stats
    collector.last_error = last_error[:MAX_ERROR_LENGTH] if last_error else None
    db.commit()


def set_mode(
    db: Session, settings: Settings, ctx: AuditContext, collector_id: int, mode: str
) -> Collector:
    """Switch observation <-> inference. Inference needs the live gate to be open."""
    collector = get_collector(db, collector_id)
    if mode == collector.mode:
        return collector
    if mode == "inference":
        gate = live_gate(db, settings)
        if not gate.model_ready:
            audit.record(
                db,
                ctx,
                "collector.mode_changed",
                target_type="collector",
                target_id=collector.id,
                outcome="denied",
                details={"to": mode, "reason": gate.reason},
            )
            db.commit()
            raise AppError("live_gate_closed", gate.reason, 409)
    audit.record(
        db,
        ctx,
        "collector.mode_changed",
        target_type="collector",
        target_id=collector.id,
        details={"from": collector.mode, "to": mode},
    )
    collector.mode = mode
    db.commit()
    return collector
