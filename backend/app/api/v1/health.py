from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from app.core.config import APP_NAME, APP_VERSION, Settings, get_settings
from app.db.session import get_engine
from app.schemas.health import LivenessOut, ReadinessOut
from app.services.health import check_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessOut)
def live() -> LivenessOut:
    """The process is running. Does not touch dependencies."""
    return LivenessOut(status="ok", service=APP_NAME, version=APP_VERSION)


@router.get(
    "/ready",
    response_model=ReadinessOut,
    responses={503: {"model": ReadinessOut, "description": "A required dependency is not ready"}},
)
def ready(
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> JSONResponse:
    """The API can serve requests: database reachable and schema at the latest migration."""
    database, migrations = check_database(engine)
    is_ready = database.status == "ok" and migrations.status == "ok"
    body = ReadinessOut(
        status="ready" if is_ready else "not_ready",
        service=APP_NAME,
        version=APP_VERSION,
        environment=settings.environment,
        components={"database": database, "migrations": migrations},
    )
    return JSONResponse(status_code=200 if is_ready else 503, content=body.model_dump())
