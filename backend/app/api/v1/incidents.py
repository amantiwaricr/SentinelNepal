from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import AnalystUser, Audit, DbSession
from app.models.alert import Alert
from app.models.incident import Incident, IncidentAlert, InvestigationNote
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.ops import AlertOut
from app.schemas.workflow import (
    AuditLogOut,
    IncidentCreate,
    IncidentDetail,
    IncidentOut,
    IncidentStatus,
    IncidentUpdate,
    LinkAlerts,
    NoteCreate,
    NoteOut,
    Severity,
)
from app.services import incidents

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _out(incident: Incident, count: int) -> IncidentOut:
    return IncidentOut.model_validate(incident).model_copy(update={"alert_count": count})


def _detail(db: DbSession, incident: Incident) -> IncidentDetail:
    alerts = db.scalars(
        select(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
        .where(IncidentAlert.incident_id == incident.id)
        .order_by(Alert.id)
    ).all()
    base = _out(incident, len(alerts)).model_dump()
    return IncidentDetail(
        **base,
        alerts=[AlertOut.model_validate(a) for a in alerts],
        allowed_transitions=sorted(incidents.TRANSITIONS[incident.status]),
    )


def _note_out(note: InvestigationNote, username: str) -> NoteOut:
    return NoteOut(
        id=note.id,
        incident_id=note.incident_id,
        author_id=note.author_id,
        author_username=username,
        body=note.body,
        created_at=note.created_at,
    )


@router.get("", response_model=Page[IncidentOut])
def list_incidents(
    _: AnalystUser,
    db: DbSession,
    paging: Annotated[PageParams, Depends(page_params)],
    status: IncidentStatus | None = None,
    severity: Severity | None = None,
    assigned_to: int | None = None,
) -> Page[IncidentOut]:
    conditions = [
        column == value
        for column, value in (
            (Incident.status, status),
            (Incident.severity, severity),
            (Incident.assigned_to, assigned_to),
        )
        if value is not None
    ]
    total = db.scalar(select(func.count()).select_from(Incident).where(*conditions)) or 0
    rows = db.scalars(
        select(Incident)
        .where(*conditions)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    counts = incidents.alert_counts(db, [i.id for i in rows])
    return Page(
        items=[_out(i, counts.get(i.id, 0)) for i in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.post("", response_model=IncidentDetail, status_code=201)
def create_incident(body: IncidentCreate, ctx: Audit, db: DbSession) -> IncidentDetail:
    incident = incidents.create_incident(
        db,
        ctx,
        title=body.title,
        description=body.description,
        severity=body.severity,
        alert_ids=body.alert_ids,
        assigned_to=body.assigned_to,
    )
    return _detail(db, incident)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, _: AnalystUser, db: DbSession) -> IncidentDetail:
    return _detail(db, incidents.get_incident(db, incident_id))


@router.patch("/{incident_id}", response_model=IncidentDetail)
def update_incident(
    incident_id: int, body: IncidentUpdate, ctx: Audit, db: DbSession
) -> IncidentDetail:
    # Only fields the client actually sent are changed (so "assigned_to": null unassigns).
    changes = body.model_dump(include=body.model_fields_set)
    return _detail(db, incidents.update_incident(db, ctx, incident_id, changes))


@router.post("/{incident_id}/alerts", response_model=IncidentDetail)
def link_alerts(incident_id: int, body: LinkAlerts, ctx: Audit, db: DbSession) -> IncidentDetail:
    incidents.link_alerts(db, ctx, incident_id, body.alert_ids)
    return _detail(db, incidents.get_incident(db, incident_id))


@router.get("/{incident_id}/notes", response_model=list[NoteOut])
def list_notes(incident_id: int, _: AnalystUser, db: DbSession) -> list[NoteOut]:
    incidents.get_incident(db, incident_id)
    rows = db.execute(
        select(InvestigationNote, User.username)
        .join(User, User.id == InvestigationNote.author_id)
        .where(InvestigationNote.incident_id == incident_id)
        .order_by(InvestigationNote.id)
    ).all()
    return [_note_out(note, username) for note, username in rows]


@router.post("/{incident_id}/notes", response_model=NoteOut, status_code=201)
def add_note(incident_id: int, body: NoteCreate, ctx: Audit, db: DbSession) -> NoteOut:
    note = incidents.add_note(db, ctx, incident_id, body.body)
    return _note_out(note, ctx.actor.username if ctx.actor else "")


@router.get("/{incident_id}/history", response_model=list[AuditLogOut])
def incident_history(incident_id: int, _: AnalystUser, db: DbSession) -> list[AuditLogOut]:
    """Audit entries about this incident, so the team can review previous actions."""
    return [AuditLogOut.model_validate(e) for e in incidents.history(db, incident_id)]
