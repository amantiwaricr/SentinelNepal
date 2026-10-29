from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import UnaryExpression, cast, func, select
from sqlalchemy.dialects.postgresql import INET

from app.api.deps import AnalystUser, Audit, DbSession
from app.core.errors import AppError
from app.models.alert import Alert
from app.models.incident import Incident, IncidentAlert
from app.models.model_version import ModelVersion
from app.models.recommendation import Recommendation
from app.schemas.common import (
    AlertSource,
    AlertStatus,
    AttackCategory,
    Page,
    PageParams,
    Severity,
    page_params,
)
from app.schemas.ops import (
    AlertDetail,
    AlertOut,
    AlertStatusUpdate,
    IncidentBrief,
    ModelBrief,
    RecommendationOut,
)
from app.services import alerts
from app.services.investigation import in_network, parse_ip, parse_network

router = APIRouter(prefix="/alerts", tags=["alerts"])

SORTS: dict[str, tuple[UnaryExpression[Any], ...]] = {
    "-created_at": (Alert.created_at.desc(), Alert.id.desc()),
    "created_at": (Alert.created_at.asc(), Alert.id.asc()),
    "-attack_score": (Alert.attack_score.desc(), Alert.id.desc()),
    "attack_score": (Alert.attack_score.asc(), Alert.id.asc()),
}


@router.get("", response_model=Page[AlertOut])
def list_alerts(
    _: AnalystUser,
    db: DbSession,
    paging: Annotated[PageParams, Depends(page_params)],
    src_ip: str | None = None,
    dst_ip: str | None = None,
    cidr: Annotated[str | None, Query(description="Source or destination within")] = None,
    category: AttackCategory | None = None,
    severity: Severity | None = None,
    status: AlertStatus | None = None,
    source: AlertSource | None = None,
    run_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: Literal["-created_at", "created_at", "-attack_score", "attack_score"] = "-created_at",
) -> Page[AlertOut]:
    conditions = []
    if src_ip:
        conditions.append(Alert.src_ip == cast(str(parse_ip(src_ip)), INET))
    if dst_ip:
        conditions.append(Alert.dst_ip == cast(str(parse_ip(dst_ip)), INET))
    if cidr:
        conditions.append(in_network(parse_network(cidr)))
    for column, value in (
        (Alert.predicted_category, category),
        (Alert.severity, severity),
        (Alert.status, status),
        (Alert.source, source),
        (Alert.analysis_run_id, run_id),
    ):
        if value is not None:
            conditions.append(column == value)
    if created_from:
        conditions.append(Alert.created_at >= created_from)
    if created_to:
        conditions.append(Alert.created_at < created_to)

    total = db.scalar(select(func.count()).select_from(Alert).where(*conditions)) or 0
    rows = db.scalars(
        select(Alert)
        .where(*conditions)
        .order_by(*SORTS[sort])
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[AlertOut.model_validate(a) for a in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: int, _: AnalystUser, db: DbSession) -> AlertDetail:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise AppError("not_found", "Alert not found", 404)
    model = db.get(ModelVersion, alert.model_version_id)
    recommendations = db.scalars(
        select(Recommendation)
        .where(Recommendation.alert_id == alert.id)
        .order_by(Recommendation.id)
    ).all()
    incidents = db.scalars(
        select(Incident)
        .join(IncidentAlert, IncidentAlert.incident_id == Incident.id)
        .where(IncidentAlert.alert_id == alert.id)
        .order_by(Incident.id)
    ).all()
    return AlertDetail.model_validate(
        {
            **AlertOut.model_validate(alert).model_dump(),
            "evidence": alert.evidence,
            "model": ModelBrief.model_validate(model),
            "recommendations": [RecommendationOut.model_validate(r) for r in recommendations],
            "incidents": [IncidentBrief.model_validate(i) for i in incidents],
        }
    )


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int, body: AlertStatusUpdate, _: AnalystUser, ctx: Audit, db: DbSession
) -> AlertOut:
    return AlertOut.model_validate(alerts.set_status(db, ctx, alert_id, body.status))
