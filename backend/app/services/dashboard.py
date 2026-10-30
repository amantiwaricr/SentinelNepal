"""Dashboard figures, computed from stored data only."""

from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select, true
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.alert import Alert
from app.models.analysis import DatasetAnalysisRun
from app.models.incident import Incident
from app.models.model_version import ModelVersion

SOURCES = {"all": None, "dataset": ("dataset",), "live": ("live", "replay")}
ACTIVITY_DAYS = 14


def _grouped(
    db: Session, column: Any, condition: ColumnElement[bool], limit: int | None = None
) -> dict[str, int]:
    stmt = (
        select(column, func.count())
        .where(condition, column.is_not(None))
        .group_by(column)
        .order_by(func.count().desc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return {str(k): int(n) for k, n in db.execute(stmt).all()}


def summary(db: Session, source: str, model_profiles: tuple[str, ...]) -> dict[str, Any]:
    """``model_profiles``: the feature profiles whose active model scores this source's
    alerts (dataset analysis and live/replay use different models)."""
    sources = SOURCES[source]
    condition = Alert.source.in_(sources) if sources else true()
    since = utcnow() - timedelta(days=ACTIVITY_DAYS)
    day = func.date_trunc("day", Alert.created_at)
    activity = db.execute(
        select(day, func.count())
        .where(condition, Alert.created_at >= since)
        .group_by(day)
        .order_by(day)
    ).all()
    active_models = db.scalars(
        select(ModelVersion)
        .where(ModelVersion.is_active, ModelVersion.feature_profile.in_(model_profiles))
        .order_by(ModelVersion.feature_profile)
    ).all()
    return {
        "source": source,
        "generated_at": utcnow(),
        "alerts_total": db.scalar(select(func.count()).select_from(Alert).where(condition)) or 0,
        "alerts_new": db.scalar(
            select(func.count()).select_from(Alert).where(condition, Alert.status == "new")
        )
        or 0,
        "alerts_by_severity": _grouped(db, Alert.severity, condition),
        "alerts_by_category": _grouped(db, Alert.predicted_category, condition),
        "alerts_by_status": _grouped(db, Alert.status, condition),
        "alerts_by_source": _grouped(db, Alert.source, condition),
        "alert_activity_by_day": [{"day": d, "count": int(n)} for d, n in activity],
        "top_source_ips": _grouped(db, Alert.src_ip, condition, limit=10),
        "incidents_by_status": _grouped(db, Incident.status, true()),
        "analysis_runs_by_status": _grouped(db, DatasetAnalysisRun.status, true()),
        "active_models": [
            {
                "id": m.id,
                "feature_profile": m.feature_profile,
                "name": m.name,
                "version": m.version,
                "alert_threshold": m.alert_threshold,
            }
            for m in active_models
        ],
    }
