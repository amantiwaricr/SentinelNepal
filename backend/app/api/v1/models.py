from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, AnalystUser, Audit, DbSession
from app.models.model_version import ModelVersion
from app.schemas.ops import ModelVersionOut
from app.services import models

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelVersionOut])
def list_models(_: AnalystUser, db: DbSession) -> list[ModelVersionOut]:
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    return [ModelVersionOut.model_validate(m) for m in rows]


@router.get("/active", response_model=list[ModelVersionOut])
def active_models(_: AnalystUser, db: DbSession) -> list[ModelVersionOut]:
    rows = db.scalars(select(ModelVersion).where(ModelVersion.is_active)).all()
    return [ModelVersionOut.model_validate(m) for m in rows]


@router.post("/{model_id}/activate", response_model=ModelVersionOut)
def activate(model_id: int, _: AdminUser, ctx: Audit, db: DbSession) -> ModelVersionOut:
    return ModelVersionOut.model_validate(models.activate_model(db, ctx, model_id))
