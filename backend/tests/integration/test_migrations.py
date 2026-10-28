import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.services.health import migration_head


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_upgrade_downgrade_upgrade_on_clean_database(
    engine: Engine, alembic_config: Config
) -> None:
    assert _tables(engine) == set()

    command.upgrade(alembic_config, "head")
    assert {"users", "alembic_version"} <= _tables(engine)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == migration_head()

    command.downgrade(alembic_config, "base")
    assert _tables(engine) <= {"alembic_version"}

    command.upgrade(alembic_config, "head")
    assert "users" in _tables(engine)


def _insert_user(engine: Engine, username: str, role: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES (:u, 'x', :r)"),
            {"u": username, "r": role},
        )


def test_users_constraints(migrated_engine: Engine) -> None:
    _insert_user(migrated_engine, "sita", "analyst")

    with pytest.raises(IntegrityError):
        _insert_user(migrated_engine, "sita", "admin")  # duplicate username
    with pytest.raises(IntegrityError):
        _insert_user(migrated_engine, "Ram", "admin")  # must be lower-case
    with pytest.raises(IntegrityError):
        _insert_user(migrated_engine, "hari", "root")  # unknown role


def test_timestamps_are_timezone_aware(migrated_engine: Engine) -> None:
    _insert_user(migrated_engine, "gita", "admin")
    with migrated_engine.connect() as conn:
        created = conn.execute(
            text("SELECT created_at FROM users WHERE username = 'gita'")
        ).scalar_one()
    assert created.tzinfo is not None
