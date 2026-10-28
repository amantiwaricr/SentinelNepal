"""Readiness checks for the backend's dependencies.

Each check reports what it actually observed; a failure is reported as such rather than
being hidden behind a generic "ok".
"""

import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.health import ComponentStatus

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
