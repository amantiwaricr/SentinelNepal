from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.models.audit import AuditLog
from app.schemas.common import Page, PageParams, page_params
from app.schemas.workflow import AuditLogOut

# Read-only by design: there are no create, update, or delete endpoints for audit records.
router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    _: AdminUser,
    db: DbSession,
    paging: Annotated[PageParams, Depends(page_params)],
    actor: Annotated[str | None, Query(max_length=64, description="Username")] = None,
    action: Annotated[
        str | None, Query(max_length=64, description="Exact action or prefix, e.g. 'firewall.'")
    ] = None,
    target_type: Annotated[str | None, Query(max_length=32)] = None,
    target_id: Annotated[str | None, Query(max_length=64)] = None,
    outcome: Literal["success", "failure", "denied"] | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> Page[AuditLogOut]:
    conditions = []
    if actor:
        conditions.append(AuditLog.actor_label == actor.strip().lower())
    if action:
        if action.endswith("."):
            conditions.append(AuditLog.action.startswith(action, autoescape=True))
        else:
            conditions.append(AuditLog.action == action)
    for column, value in (
        (AuditLog.target_type, target_type),
        (AuditLog.target_id, target_id),
        (AuditLog.outcome, outcome),
    ):
        if value is not None:
            conditions.append(column == value)
    if occurred_from:
        conditions.append(AuditLog.occurred_at >= occurred_from)
    if occurred_to:
        conditions.append(AuditLog.occurred_at < occurred_to)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    rows = db.scalars(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.id.desc())
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[AuditLogOut.model_validate(r) for r in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )
