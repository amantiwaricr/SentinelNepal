"""Incidents are created and moved through their lifecycle by people only. No code path
creates an incident from a model prediction, and new incidents always start as "new"."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import utcnow
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.incident import Incident, IncidentAlert, InvestigationNote
from app.models.user import User
from app.services import audit
from app.services.audit import AuditContext

TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"under_investigation", "false_positive"}),
    "under_investigation": frozenset({"confirmed", "false_positive", "resolved"}),
    "confirmed": frozenset({"resolved", "under_investigation"}),
    "false_positive": frozenset({"under_investigation", "resolved"}),
    "resolved": frozenset({"under_investigation"}),  # reopen
}
MAX_LINKED_PER_CALL = 500


def get_incident(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise AppError("not_found", "Incident not found", 404)
    return incident


def _active_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("invalid_assignee", "Assignee must be an active user", 422)
    return user


def _link(db: Session, ctx: AuditContext, incident: Incident, alert_ids: list[int]) -> list[int]:
    if len(alert_ids) > MAX_LINKED_PER_CALL:
        raise AppError("too_many_alerts", f"At most {MAX_LINKED_PER_CALL} alerts per request", 422)
    wanted = sorted(set(alert_ids))
    found = db.scalars(select(Alert).where(Alert.id.in_(wanted))).all()
    missing = sorted(set(wanted) - {a.id for a in found})
    if missing:
        raise AppError("not_found", f"Alerts not found: {missing[:20]}", 404)
    already = set(
        db.scalars(
            select(IncidentAlert.alert_id).where(
                IncidentAlert.incident_id == incident.id, IncidentAlert.alert_id.in_(wanted)
            )
        ).all()
    )
    linked = []
    for alert in found:
        if alert.id in already:
            continue
        db.add(IncidentAlert(incident_id=incident.id, alert_id=alert.id, linked_by=_actor_id(ctx)))
        alert.status = "linked"
        linked.append(alert.id)
    return linked


def _actor_id(ctx: AuditContext) -> int:
    if ctx.actor is None:
        raise AppError("forbidden", "Only signed-in users may change incidents", 403)
    return ctx.actor.id


def create_incident(
    db: Session,
    ctx: AuditContext,
    *,
    title: str,
    description: str,
    severity: str,
    alert_ids: list[int],
    assigned_to: int | None,
) -> Incident:
    if assigned_to is not None:
        _active_user(db, assigned_to)
    incident = Incident(
        title=title,
        description=description,
        severity=severity,
        status="new",  # always: confirming an incident is a human decision
        created_by=_actor_id(ctx),
        assigned_to=assigned_to,
    )
    db.add(incident)
    db.flush()
    linked = _link(db, ctx, incident, alert_ids)
    audit.record(
        db,
        ctx,
        "incident.created",
        target_type="incident",
        target_id=incident.id,
        details={"severity": severity, "linked_alerts": linked, "assigned_to": assigned_to},
    )
    db.commit()
    return incident


def update_incident(
    db: Session, ctx: AuditContext, incident_id: int, changes: dict[str, Any]
) -> Incident:
    incident = get_incident(db, incident_id)
    if "status" in changes and changes["status"] != incident.status:
        new = changes["status"]
        if new not in TRANSITIONS[incident.status]:
            raise AppError(
                "invalid_transition",
                f"Cannot move an incident from {incident.status} to {new}",
                409,
                details={"allowed": sorted(TRANSITIONS[incident.status])},
            )
        audit.record(
            db,
            ctx,
            "incident.status_changed",
            target_type="incident",
            target_id=incident.id,
            details={"from": incident.status, "to": new},
        )
        incident.status = new
        incident.resolved_at = utcnow() if new == "resolved" else None
    if "assigned_to" in changes and changes["assigned_to"] != incident.assigned_to:
        if changes["assigned_to"] is not None:
            _active_user(db, changes["assigned_to"])
        audit.record(
            db,
            ctx,
            "incident.assigned",
            target_type="incident",
            target_id=incident.id,
            details={"from": incident.assigned_to, "to": changes["assigned_to"]},
        )
        incident.assigned_to = changes["assigned_to"]
    edited: dict[str, Any] = {}
    for field in ("title", "description", "severity"):
        if (
            field in changes
            and changes[field] is not None
            and changes[field] != getattr(incident, field)
        ):
            edited[field] = {"from": getattr(incident, field), "to": changes[field]}
            setattr(incident, field, changes[field])
    if edited:
        # Free-text values are not copied into the audit log; only which fields changed.
        summary: dict[str, Any] = {
            k: v if k == "severity" else "changed" for k, v in edited.items()
        }
        audit.record(
            db,
            ctx,
            "incident.updated",
            target_type="incident",
            target_id=incident.id,
            details=summary,
        )
    db.commit()
    return incident


def link_alerts(
    db: Session, ctx: AuditContext, incident_id: int, alert_ids: list[int]
) -> list[int]:
    incident = get_incident(db, incident_id)
    linked = _link(db, ctx, incident, alert_ids)
    if linked:
        audit.record(
            db,
            ctx,
            "incident.alerts_linked",
            target_type="incident",
            target_id=incident.id,
            details={"alert_ids": linked},
        )
    db.commit()
    return linked


def add_note(db: Session, ctx: AuditContext, incident_id: int, body: str) -> InvestigationNote:
    incident = get_incident(db, incident_id)
    note = InvestigationNote(incident_id=incident.id, author_id=_actor_id(ctx), body=body)
    db.add(note)
    db.flush()
    audit.record(
        db,
        ctx,
        "incident.note_added",
        target_type="incident",
        target_id=incident.id,
        details={"note_id": note.id, "length": len(body)},
    )
    db.commit()
    return note


def alert_counts(db: Session, incident_ids: list[int]) -> dict[int, int]:
    if not incident_ids:
        return {}
    rows = db.execute(
        select(IncidentAlert.incident_id, func.count())
        .where(IncidentAlert.incident_id.in_(incident_ids))
        .group_by(IncidentAlert.incident_id)
    ).all()
    return {int(i): int(n) for i, n in rows}


def history(db: Session, incident_id: int) -> list[AuditLog]:
    get_incident(db, incident_id)
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.target_type == "incident", AuditLog.target_id == str(incident_id))
            .order_by(AuditLog.id)
        ).all()
    )
