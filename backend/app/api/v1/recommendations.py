from fastapi import APIRouter

from app.api.deps import AnalystUser, DbSession
from app.core.errors import AppError
from app.models.alert import Alert
from app.schemas.ops import RecommendationOut
from app.schemas.recommendations import EvidenceRequirement, RuleOut
from app.services.recommendations.engine import ensure_for_alert
from app.services.recommendations.evidence import CHECKS
from app.services.recommendations.rules import CATALOGUE

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(alert_id: int, _: AnalystUser, db: DbSession) -> list[RecommendationOut]:
    """Recommendations for an alert; generated from the rule catalogue on first request."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise AppError("not_found", "Alert not found", 404)
    return [RecommendationOut.model_validate(r) for r in ensure_for_alert(db, alert)]


@router.get("/rules", response_model=list[RuleOut])
def list_rules(_: AnalystUser) -> list[RuleOut]:
    """The full rule catalogue, so analysts can see why each recommendation is made."""
    return [
        RuleOut(
            rule_id=rule.rule_id,
            version=rule.version,
            group=rule.group,
            categories=sorted(rule.categories),
            kind=rule.kind,
            heuristic=rule.heuristic_trigger is not None,
            action=rule.action,
            reason=rule.reason,
            required_evidence=[
                EvidenceRequirement(name=name, description=CHECKS[name].description)
                for name in rule.required_evidence
            ],
            priority=rule.priority,
            limitations=rule.limitations,
            requires_human_approval=rule.requires_human_approval,
        )
        for rule in CATALOGUE
    ]
