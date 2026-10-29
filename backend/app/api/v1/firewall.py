from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import AdminUser, AnalystUser, AppSettings, Audit, DbSession
from app.core.errors import AppError
from app.models.firewall import FirewallActionResult, FirewallRequest
from app.schemas.common import FirewallStatus, Page, PageParams, page_params
from app.schemas.workflow import (
    FirewallActionResultOut,
    FirewallApprove,
    FirewallReject,
    FirewallRequestCreate,
    FirewallRequestOut,
    FirewallRevoke,
    FirewallStatusOut,
)
from app.services import firewall

router = APIRouter(prefix="/firewall", tags=["firewall"])


def _out(db: DbSession, request: FirewallRequest) -> FirewallRequestOut:
    results = db.scalars(
        select(FirewallActionResult)
        .where(FirewallActionResult.request_id == request.id)
        .order_by(FirewallActionResult.id)
    ).all()
    out = FirewallRequestOut.model_validate(request)
    return out.model_copy(
        update={
            "results": [FirewallActionResultOut.model_validate(r) for r in results],
            # Only a helper-confirmed apply counts; status alone never implies a block.
            "applied": any(r.operation == "apply" and r.success for r in results)
            and request.status == "active",
        }
    )


@router.get("/requests", response_model=Page[FirewallRequestOut])
def list_requests(
    _: AnalystUser,
    db: DbSession,
    paging: Annotated[PageParams, Depends(page_params)],
    status: FirewallStatus | None = None,
) -> Page[FirewallRequestOut]:
    conditions = [FirewallRequest.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(FirewallRequest).where(*conditions)) or 0
    rows = db.scalars(
        select(FirewallRequest)
        .where(*conditions)
        .order_by(FirewallRequest.id.desc())
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[_out(db, r) for r in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.get("/requests/{request_id}", response_model=FirewallRequestOut)
def get_request(request_id: int, _: AnalystUser, db: DbSession) -> FirewallRequestOut:
    request = db.get(FirewallRequest, request_id)
    if request is None:
        raise AppError("not_found", "Firewall request not found", 404)
    return _out(db, request)


@router.post("/requests", response_model=FirewallRequestOut, status_code=201)
def create_request(
    body: FirewallRequestCreate, ctx: Audit, db: DbSession, settings: AppSettings
) -> FirewallRequestOut:
    # Role check is in the service: analysts may request only if the setting allows it.
    request = firewall.create_request(
        db,
        settings,
        ctx,
        target=body.target,
        duration_seconds=body.duration_seconds,
        reason=body.reason,
        alert_id=body.alert_id,
        incident_id=body.incident_id,
        dry_run=body.dry_run,
    )
    return _out(db, request)


@router.post("/requests/{request_id}/approve", response_model=FirewallRequestOut)
def approve(
    request_id: int,
    body: FirewallApprove,
    _: AdminUser,
    ctx: Audit,
    db: DbSession,
    settings: AppSettings,
) -> FirewallRequestOut:
    request = firewall.approve(
        db, settings, ctx, request_id, confirm_target=body.confirm_target, note=body.note
    )
    return _out(db, request)


@router.post("/requests/{request_id}/reject", response_model=FirewallRequestOut)
def reject(
    request_id: int, body: FirewallReject, _: AdminUser, ctx: Audit, db: DbSession
) -> FirewallRequestOut:
    return _out(db, firewall.reject(db, ctx, request_id, note=body.note))


@router.post("/requests/{request_id}/revoke", response_model=FirewallRequestOut)
def revoke(
    request_id: int, body: FirewallRevoke, _: AdminUser, ctx: Audit, db: DbSession
) -> FirewallRequestOut:
    return _out(db, firewall.revoke(db, ctx, request_id, note=body.note))


@router.get("/status", response_model=FirewallStatusOut)
def status(_: AdminUser, settings: AppSettings) -> FirewallStatusOut:
    return FirewallStatusOut(
        helper="not_configured",
        detail="The restricted nftables helper is added in Phase 7. Approved requests are "
        "recorded, but nothing is applied to any firewall.",
        protected_networks=settings.firewall_protected_networks,
        max_duration_seconds=settings.firewall_max_duration_seconds,
        self_approval_allowed=settings.firewall_allow_self_approval,
    )
