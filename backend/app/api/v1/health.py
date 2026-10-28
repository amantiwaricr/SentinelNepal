from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from app.api.deps import AnalystUser, AppSettings, DbSession
from app.core.config import APP_NAME, APP_VERSION
from app.db.session import get_engine
from app.schemas.health import ComponentsOut, LivenessOut, ReadinessOut
from app.services.health import check_components, check_database

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
    settings: AppSettings,
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


@router.get("/components", response_model=ComponentsOut)
def components(
    request: Request,
    _: AnalystUser,
    db: DbSession,
    settings: AppSettings,
    engine: Annotated[Engine, Depends(get_engine)],
) -> ComponentsOut:
    """Detailed status for signed-in users (it reveals model and queue details)."""
    worker = request.app.state.analysis_worker
    return ComponentsOut(
        components=check_components(
            db, engine, settings, worker_alive=None if worker is None else worker.alive
        )
    )
