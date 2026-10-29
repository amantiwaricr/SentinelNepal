"""Collects the facts about an alert and stores the recommendations the rules produce.

Recommendations are generated the first time someone looks at an alert, not for every
alert at analysis time: most dataset alerts are never opened, and generating on view uses
the counts of all alerts stored by then (a whole analysis run rather than the part processed
so far). The stored rows keep the rule version and the evidence as observed, so a
recommendation can always be explained later even if the rules or counts change.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, cast, func, select
from sqlalchemy.dialects.postgresql import INET, insert
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.model_version import ModelVersion
from app.models.recommendation import Recommendation
from app.services.models import category_precision
from app.services.recommendations.evidence import AlertFacts
from app.services.recommendations.rules import recommend

LIVE_WINDOW = timedelta(days=1)


def _scope(alert: Alert) -> ColumnElement[bool]:
    """Which other alerts count as related: the same dataset run, or for live and replayed
    traffic the same source type within a day either side."""
    if alert.analysis_run_id is not None:
        return Alert.analysis_run_id == alert.analysis_run_id
    return (
        (Alert.source == alert.source)
        & (Alert.created_at >= alert.created_at - LIVE_WINDOW)
        & (Alert.created_at <= alert.created_at + LIVE_WINDOW)
    )


def facts_for(db: Session, alert: Alert) -> AlertFacts:
    model = db.get(ModelVersion, alert.model_version_id)
    precision, precision_source = category_precision(model.metrics if model else {})
    evidence: dict[str, Any] = alert.evidence or {}

    alerts_from_source = ports_from_source = to_same_target = None
    if alert.src_ip is not None:
        scope = _scope(alert) & (Alert.src_ip == cast(str(alert.src_ip), INET))
        alerts_from_source, ports_from_source = db.execute(
            select(func.count(), func.count(func.distinct(Alert.dst_port)))
            .select_from(Alert)
            .where(scope)
        ).one()
        if alert.dst_ip is not None and alert.dst_port is not None:
            to_same_target = db.scalar(
                select(func.count())
                .select_from(Alert)
                .where(
                    scope,
                    Alert.dst_ip == cast(str(alert.dst_ip), INET),
                    Alert.dst_port == alert.dst_port,
                )
            )

    return AlertFacts(
        category=alert.predicted_category,
        attack_score=alert.attack_score,
        default_decision=evidence.get("default_decision"),
        src_ip=None if alert.src_ip is None else str(alert.src_ip),
        dst_ip=None if alert.dst_ip is None else str(alert.dst_ip),
        dst_port=alert.dst_port,
        service=alert.service,
        category_precision=precision.get(alert.predicted_category),
        precision_source=precision_source,
        alerts_from_source=alerts_from_source,
        distinct_ports_from_source=ports_from_source,
        alerts_to_same_target=to_same_target,
    )


def _stored(db: Session, alert_id: int) -> list[Recommendation]:
    return list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.alert_id == alert_id)
            .order_by(Recommendation.id)
        ).all()
    )


def ensure_for_alert(db: Session, alert: Alert) -> list[Recommendation]:
    """The alert's recommendations, generating and storing them on first use."""
    existing = _stored(db, alert.id)
    if existing:
        return existing
    drafts = recommend(facts_for(db, alert))
    # ON CONFLICT DO NOTHING: if two requests generate at once, the first insert wins and
    # both return the same rows.
    db.execute(
        insert(Recommendation)
        .values([{"alert_id": alert.id, **draft.__dict__} for draft in drafts])
        .on_conflict_do_nothing(constraint="uq_recommendations_alert_rule")
    )
    db.commit()
    return _stored(db, alert.id)
