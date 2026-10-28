"""Alerts: built from predictions that cross the model's alert threshold."""

from datetime import datetime
from typing import Any

from sentinel_ml.inference import Prediction
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.alert import Alert
from app.models.model_version import ModelVersion
from app.services import audit
from app.services.audit import AuditContext

# Starting severity per predicted category, a transparent heuristic rather than a measured
# risk: categories associated with code execution or service outage start "high".
SEVERITY_BY_CATEGORY = {
    "Exploits": "high",
    "Shellcode": "high",
    "Backdoor": "high",
    "Worms": "high",
    "DoS": "high",
    "Reconnaissance": "medium",
    "Fuzzers": "medium",
    "Analysis": "medium",
    "Generic": "medium",
}
LOWER = {"critical": "high", "high": "medium", "medium": "low", "low": "low"}
STRONG_SCORE = 0.8
SEVERITY_RULE = (
    "Starts from the predicted category; lowered one level when the attack score is below "
    f"{STRONG_SCORE}. A heuristic for triage order, not a measure of risk."
)
# Statuses an analyst may set directly; "linked" is set by linking the alert to an incident.
SETTABLE_STATUSES = ("new", "acknowledged", "dismissed")


def severity_for(category: str, attack_score: float) -> str:
    base = SEVERITY_BY_CATEGORY.get(category, "medium")
    return base if attack_score >= STRONG_SCORE else LOWER[base]


def should_alert(prediction: Prediction, threshold: float | None) -> bool:
    """With a validation-chosen threshold, alert on the attack score; without one, fall
    back to the model's default decision (highest-scoring class is an attack)."""
    if threshold is None:
        return prediction.is_suspicious
    return prediction.attack_score >= threshold


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _datetime_or_none(value: object) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None


def alert_from_prediction(
    prediction: Prediction,
    model: ModelVersion,
    *,
    source: str,
    dedup_key: str,
    analysis_run_id: int | None = None,
) -> Alert:
    category = (
        prediction.predicted_category
        if prediction.is_suspicious
        else prediction.top_attack_category
    )
    meta = prediction.metadata
    top_scores = dict(
        sorted(prediction.class_scores.items(), key=lambda item: item[1], reverse=True)[:3]
    )
    evidence: dict[str, Any] = {
        "class_scores_top3": top_scores,
        "default_decision": prediction.predicted_category,
        "alert_threshold": model.alert_threshold,
        "features": prediction.features,
        "imputed_features": prediction.imputed_features,
        "unknown_categories": prediction.unknown_categories,
        "severity_rule": SEVERITY_RULE,
        "note": "Model scores are uncalibrated; this alert is a prediction, not proof.",
    }
    return Alert(
        source=source,
        analysis_run_id=analysis_run_id,
        model_version_id=model.id,
        observed_at=_datetime_or_none(meta.get("start_time")),
        src_ip=meta.get("src_ip"),
        dst_ip=meta.get("dst_ip"),
        src_port=_int_or_none(meta.get("src_port")),
        dst_port=_int_or_none(meta.get("dst_port")),
        protocol=str(prediction.features.get("proto") or "") or None,
        service=str(prediction.features.get("service") or "") or None,
        predicted_category=category,
        attack_score=prediction.attack_score,
        severity=severity_for(category, prediction.attack_score),
        status="new",
        evidence=evidence,
        dedup_key=dedup_key,
    )


def set_status(db: Session, ctx: AuditContext, alert_id: int, status: str) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise AppError("not_found", "Alert not found", 404)
    if status not in SETTABLE_STATUSES:
        raise AppError("invalid_status", f"Status must be one of {list(SETTABLE_STATUSES)}", 422)
    if alert.status == "linked":
        raise AppError("conflict", "Alert is linked to an incident; manage it there", 409)
    if alert.status != status:
        audit.record(
            db,
            ctx,
            "alert.status_changed",
            target_type="alert",
            target_id=alert.id,
            details={"from": alert.status, "to": status},
        )
        alert.status = status
    db.commit()
    return alert
