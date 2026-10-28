"""Readiness checks for the backend's dependencies.

Each check reports what it actually observed; a failure is reported as such rather than
being hidden behind a generic "ok".
"""

import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sentinel_ml.artifacts import MODEL_FILE
from sentinel_ml.features.dataset import sha256_file
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.analysis import DatasetAnalysisRun
from app.models.collector import Collector
from app.schemas.health import ComponentStatus
from app.services.models import active_model, artifact_path

logger = logging.getLogger(__name__)

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def migration_head() -> str | None:
    config = Config(str(ALEMBIC_INI))
    return ScriptDirectory.from_config(config).get_current_head()


def check_database(engine: Engine) -> tuple[ComponentStatus, ComponentStatus]:
    """Return (database, migrations) component statuses."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            # Check the table exists first: querying a missing table is a parse-time error.
            has_version_table = conn.execute(
                text("SELECT to_regclass('alembic_version') IS NOT NULL")
            ).scalar_one()
            current = (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
                if has_version_table
                else None
            )
    except SQLAlchemyError as exc:
        # Log the driver error for operators; the API response only says it is unreachable,
        # so connection strings or hostnames never leak to clients.
        logger.warning("Database readiness check failed: %s", exc.__class__.__name__)
        database = ComponentStatus(status="unavailable", detail="Database is unreachable")
        migrations = ComponentStatus(status="unknown", detail="Database is unreachable")
        return database, migrations

    database = ComponentStatus(status="ok")
    head = migration_head()
    if current is None:
        migrations = ComponentStatus(
            status="pending", detail="No migrations applied; run 'alembic upgrade head'"
        )
    elif current != head:
        migrations = ComponentStatus(
            status="pending",
            detail=f"Database at revision {current}, code expects {head}",
        )
    else:
        migrations = ComponentStatus(status="ok", detail=f"At revision {current}")
    return database, migrations


def check_components(
    db: Session, engine: Engine, settings: Settings, *, worker_alive: bool | None
) -> dict[str, ComponentStatus]:
    database, migrations = check_database(engine)
    components = {"database": database, "migrations": migrations}

    model = active_model(db, settings.dataset_model_profile)
    if model is None:
        components["dataset_model"] = ComponentStatus(
            status="unavailable", detail="No active model; register one with python -m app.cli"
        )
    else:
        label = f"{model.name} {model.version}"
        try:
            path = artifact_path(settings, model.artifact_dir) / MODEL_FILE
            intact = path.is_file() and sha256_file(path) == model.artifact_sha256
        except AppError:
            intact = False
        components["dataset_model"] = (
            ComponentStatus(status="ok", detail=f"{label}; file matches registered SHA-256")
            if intact
            else ComponentStatus(status="unavailable", detail=f"{label}; file missing or modified")
        )

    queued = db.scalar(
        select(func.count())
        .select_from(DatasetAnalysisRun)
        .where(DatasetAnalysisRun.status.in_(("queued", "running")))
    )
    if worker_alive is None:
        components["analysis_worker"] = ComponentStatus(
            status="not_configured", detail="Disabled by ANALYSIS_WORKER_ENABLED"
        )
    else:
        components["analysis_worker"] = ComponentStatus(
            status="ok" if worker_alive else "unavailable",
            detail=f"{queued} run(s) queued or running",
        )
    components["firewall_helper"] = ComponentStatus(
        status="not_configured", detail="The firewall helper is added in Phase 7"
    )
    collectors = db.scalar(select(func.count()).select_from(Collector)) or 0
    components["collectors"] = ComponentStatus(
        status="not_configured" if collectors == 0 else "unknown",
        detail="No collectors registered" if collectors == 0 else f"{collectors} registered",
    )
    return components
