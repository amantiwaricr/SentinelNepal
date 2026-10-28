from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AnalystUser, DbSession
from app.core.errors import AppError
from app.models.alert import Alert
from app.models.recommendation import Recommendation
from app.schemas.ops import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(alert_id: int, _: AnalystUser, db: DbSession) -> list[RecommendationOut]:
    """Stored recommendations for an alert. The rule engine that creates them is Phase 5."""
    if db.get(Alert, alert_id) is None:
        raise AppError("not_found", "Alert not found", 404)
    rows = db.scalars(
        select(Recommendation)
        .where(Recommendation.alert_id == alert_id)
        .order_by(Recommendation.id)
    ).all()
    return [RecommendationOut.model_validate(r) for r in rows]
