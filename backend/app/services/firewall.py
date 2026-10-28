"""Firewall block requests: request, approval, rejection, revocation.

Phase 3 implements the *decision* workflow only. Nothing is applied to any firewall until
the restricted helper exists (Phase 7), and no response ever claims that a block is in
place. The helper will re-validate every target independently.
"""

import ipaddress

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.models.alert import Alert
from app.models.firewall import FirewallRequest
from app.models.incident import Incident
from app.models.user import User
from app.services import audit
from app.services.audit import AuditContext

Network = ipaddress.IPv4Network | ipaddress.IPv6Network
MIN_PREFIX = {4: 24, 6: 64}
EXECUTION_NOTE = (
    "Approved for execution, but the firewall helper is not available yet (Phase 7): "
    "nothing has been applied to any firewall."
)
TERMINAL_FOR_REVOKE = frozenset({"revoked", "rejected", "expired", "failed"})


def validate_target(raw: str, settings: Settings) -> Network:
    try:
        network = ipaddress.ip_network(raw.strip(), strict=True)
    except ValueError:
        raise AppError(
            "invalid_target",
            "Target must be an IPv4/IPv6 address or a network address with prefix "
            "(host bits must be zero, e.g. 10.0.0.0/24)",
            422,
        ) from None
    address = network.network_address
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or (
            network.version == 4
            and network.broadcast_address == ipaddress.ip_address("255.255.255.255")
        )
    ):
        raise AppError(
            "protected_target",
            "Loopback, link-local, multicast, unspecified and "
            "reserved addresses can never be blocked",
            422,
        )
    if network.prefixlen < MIN_PREFIX[network.version]:
        raise AppError(
            "cidr_too_broad",
            f"Blocks are limited to /{MIN_PREFIX[network.version]} or narrower for "
            f"IPv{network.version}",
            422,
        )
    for protected in settings.firewall_protected_networks:
        protected_net = ipaddress.ip_network(protected, strict=False)
        if protected_net.version == network.version and protected_net.overlaps(network):
            raise AppError(
                "protected_target", "Target overlaps a protected network (e.g. lab management)", 422
            )
    return network


def _get(db: Session, request_id: int) -> FirewallRequest:
    request = db.get(FirewallRequest, request_id, with_for_update=True)
    if request is None:
        raise AppError("not_found", "Firewall request not found", 404)
    return request


def _require_admin(ctx: AuditContext) -> User:
    if ctx.actor is None or ctx.actor.role != "admin":
        raise AppError("forbidden", "Administrator role required", 403)
    return ctx.actor


def create_request(
    db: Session,
    settings: Settings,
    ctx: AuditContext,
    *,
    target: str,
    duration_seconds: int,
    reason: str,
    alert_id: int | None,
    incident_id: int | None,
    dry_run: bool,
) -> FirewallRequest:
    actor = ctx.actor
    if actor is None or (actor.role != "admin" and not settings.firewall_analysts_may_request):
        raise AppError("forbidden", "Only administrators may request blocks", 403)
    network = validate_target(target, settings)
    if duration_seconds > settings.firewall_max_duration_seconds:
        raise AppError(
            "duration_too_long",
            f"Maximum block duration is {settings.firewall_max_duration_seconds} seconds",
            422,
        )
    if alert_id is not None and db.get(Alert, alert_id) is None:
        raise AppError("not_found", "Alert not found", 404)
    if incident_id is not None and db.get(Incident, incident_id) is None:
        raise AppError("not_found", "Incident not found", 404)
    request = FirewallRequest(
        target=str(network),
        ip_version=network.version,
        reason=reason,
        alert_id=alert_id,
        incident_id=incident_id,
        requested_by=actor.id,
        status="pending",
        duration_seconds=duration_seconds,
        dry_run=dry_run,
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(
            "duplicate_request", "An open request for this target already exists", 409
        ) from None
    audit.record(
        db,
        ctx,
        "firewall.request.created",
        target_type="firewall_request",
        target_id=request.id,
        details={"target": str(network), "duration_seconds": duration_seconds, "dry_run": dry_run},
    )
    db.commit()
    return request


def approve(
    db: Session,
    settings: Settings,
    ctx: AuditContext,
    request_id: int,
    *,
    confirm_target: str,
    note: str | None,
) -> FirewallRequest:
    admin = _require_admin(ctx)
    request = _get(db, request_id)
    if request.status != "pending":
        raise AppError("invalid_state", f"Request is {request.status}, not pending", 409)
    if request.requested_by == admin.id and not settings.firewall_allow_self_approval:
        audit.record(
            db,
            ctx,
            "firewall.request.approve",
            target_type="firewall_request",
            target_id=request.id,
            outcome="denied",
            details={"reason": "self_approval"},
        )
        db.commit()
        raise AppError("self_approval", "A different administrator must approve this request", 403)
    try:
        confirmed = ipaddress.ip_network(confirm_target.strip(), strict=False)
    except ValueError:
        confirmed = None
    if confirmed is None or str(confirmed) != str(request.target):
        raise AppError(
            "confirmation_mismatch", "Type the exact target to confirm the approval", 422
        )
    # Protected networks may have changed since the request was made.
    validate_target(str(request.target), settings)
    now = utcnow()
    request.status = "approved"
    request.approved_by = admin.id
    request.approved_at = now
    request.decision_note = note
    request.expires_at = None  # set when the helper actually applies the rule (Phase 7)
    audit.record(
        db,
        ctx,
        "firewall.request.approved",
        target_type="firewall_request",
        target_id=request.id,
        details={"target": str(request.target), "execution": EXECUTION_NOTE},
    )
    db.commit()
    return request


def reject(db: Session, ctx: AuditContext, request_id: int, *, note: str) -> FirewallRequest:
    admin = _require_admin(ctx)
    request = _get(db, request_id)
    if request.status != "pending":
        raise AppError("invalid_state", f"Request is {request.status}, not pending", 409)
    request.status = "rejected"
    request.approved_by = admin.id
    request.approved_at = utcnow()
    request.decision_note = note
    audit.record(
        db, ctx, "firewall.request.rejected", target_type="firewall_request", target_id=request.id
    )
    db.commit()
    return request


def revoke(db: Session, ctx: AuditContext, request_id: int, *, note: str | None) -> FirewallRequest:
    """Idempotent: revoking an already-closed request changes nothing."""
    admin = _require_admin(ctx)
    request = _get(db, request_id)
    if request.status in TERMINAL_FOR_REVOKE:
        db.commit()
        return request
    if request.status == "pending":
        raise AppError("invalid_state", "Pending requests are rejected, not revoked", 409)
    # Phase 3: nothing was applied, so revocation completes immediately. From Phase 7 an
    # active rule goes through "revoke_requested" until the helper confirms removal.
    request.status = "revoked"
    request.revoked_by = admin.id
    request.revoked_at = utcnow()
    if note:
        request.decision_note = note
    audit.record(
        db, ctx, "firewall.request.revoked", target_type="firewall_request", target_id=request.id
    )
    db.commit()
    return request
