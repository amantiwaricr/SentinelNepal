"""Append-only audit trail. Entries are added in the caller's transaction, so an action and
its audit record are committed (or rolled back) together."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


@dataclass(frozen=True)
class AuditContext:
    actor: User | None
    ip: str | None = None
    request_id: str | None = None
    actor_type: str = "user"
    label: str | None = None

    @classmethod
    def system(cls, label: str) -> "AuditContext":
        return cls(actor=None, actor_type="system", label=label)

    @classmethod
    def anonymous(cls, ip: str | None, request_id: str | None) -> "AuditContext":
        return cls(actor=None, ip=ip, request_id=request_id, actor_type="anonymous")


def record(
    db: Session,
    ctx: AuditContext,
    action: str,
    *,
    target_type: str | None = None,
    target_id: object = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_type=ctx.actor_type,
        actor_user_id=ctx.actor.id if ctx.actor else None,
        actor_label=ctx.actor.username if ctx.actor else ctx.label,
        action=action,
        target_type=target_type,
        target_id=None if target_id is None else str(target_id),
        outcome=outcome,
        ip_address=ctx.ip,
        request_id=ctx.request_id,
        details=details or {},
    )
    db.add(entry)
    return entry
