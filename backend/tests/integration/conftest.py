import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import models as _models  # noqa: F401  (registers all tables on Base.metadata)
from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from app.models.model_version import ModelVersion
from app.models.user import User
from app.services.analyses import process_next_run
from app.services.audit import AuditContext
from app.services.health import ALEMBIC_INI
from app.services.models import register_model
from app.services.users import create_user
from tests.conftest import make_settings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.integration


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration" in str(item.path):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def database_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set; PostgreSQL integration tests not run")
    database = make_url(TEST_DATABASE_URL).database or ""
    # These tests drop and recreate the whole schema, so refuse anything that does not
    # look like a dedicated test database.
    if not database.endswith("_test"):
        pytest.fail(f"Refusing to run destructive tests against database {database!r}")
    return TEST_DATABASE_URL


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    eng = create_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    yield eng
    eng.dispose()


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture
def migrated_engine(engine: Engine, alembic_config: Config) -> Engine:
    command.upgrade(alembic_config, "head")
    return engine


# --- Application-level fixtures (Phase 3) ------------------------------------------------

DEFAULT_PASSWORD = "correct-horse-battery-1"
CSRF = {"X-Requested-With": "SentinelNepal"}


def _ensure_head(eng: Engine, config: Config) -> None:
    head = ScriptDirectory.from_config(config).get_current_head()
    with eng.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('alembic_version') IS NOT NULL")).scalar()
        current = (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if exists
            else None
        )
    if current != head:  # e.g. a migration test left the schema elsewhere
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        command.upgrade(config, "head")


def _truncate_all(eng: Engine) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with eng.begin() as conn:
        # Test-only cleanup by the table owner. The application never does this, and the
        # trigger blocks it for any normal statement (see test_audit_immutability).
        conn.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER USER"))
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        conn.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER USER"))


@pytest.fixture
def clean_db(database_url: str, alembic_config: Config) -> Iterator[Engine]:
    eng = create_engine(database_url)
    _ensure_head(eng, alembic_config)
    _truncate_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def app_settings(database_url: str, tmp_path: Path, model_artifacts: dict[str, Path]) -> Settings:
    return make_settings(
        database_url=database_url,
        analysis_worker_enabled=False,
        upload_dir=tmp_path / "uploads",
        model_artifacts_dir=model_artifacts["artifacts"],
    )


@pytest.fixture
def app(app_settings: Settings, clean_db: Engine) -> Iterator[FastAPI]:
    application = create_app(app_settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    session: Session = app.state.sessionmaker()
    yield session
    session.close()


def make_user(db: Session, username: str, role: str, password: str = DEFAULT_PASSWORD) -> User:
    return create_user(db, AuditContext.system("test"), username, password, role)


def logged_in_client(app: FastAPI, username: str, password: str = DEFAULT_PASSWORD) -> TestClient:
    client = TestClient(app, headers=CSRF)
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def anon(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, headers=CSRF) as client:
        yield client


@pytest.fixture
def admin_user(db: Session) -> User:
    return make_user(db, "admin1", "admin")


@pytest.fixture
def analyst_user(db: Session) -> User:
    return make_user(db, "analyst1", "analyst")


@pytest.fixture
def admin(app: FastAPI, admin_user: User) -> Iterator[TestClient]:
    with logged_in_client(app, admin_user.username) as client:
        yield client


@pytest.fixture
def analyst(app: FastAPI, analyst_user: User) -> Iterator[TestClient]:
    with logged_in_client(app, analyst_user.username) as client:
        yield client


# --- Model fixtures: trained once per session on SYNTHETIC data ---------------------------


@pytest.fixture(scope="session")
def model_artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """A small Random Forest trained on synthetic data, plus its reports and threshold."""
    from sentinel_ml.evaluation.threshold import select_threshold
    from sentinel_ml.testing import write_synthetic_partitioned
    from sentinel_ml.training.train import CandidateSpec, train_model

    root = tmp_path_factory.mktemp("models")
    data = write_synthetic_partitioned(root / "data", train_rows=1200, test_rows=400)
    result = train_model(
        data,
        root / "artifacts",
        root / "reports",
        rf_estimators=15,
        n_jobs=1,
        candidates=(CandidateSpec("random_forest", "random_forest", None),),
        version="synthetic",
    )
    select_threshold(result.artifact_dir, data, root / "reports", latency_calls=5)
    return {
        "artifacts": root / "artifacts",
        "reports": root / "reports",
        "artifact_dir": result.artifact_dir,
        "data": data,
    }


@pytest.fixture
def registered_model(
    db: Session, app_settings: Settings, model_artifacts: dict[str, Path]
) -> ModelVersion:
    return register_model(
        db,
        app_settings,
        AuditContext.system("test"),
        model_artifacts["artifact_dir"],
        reports_dir=model_artifacts["reports"],
        activate=True,
        allow_synthetic=True,
    )


def run_queued_analyses(app: FastAPI) -> None:
    """Process the analysis queue synchronously (the background thread is off in tests)."""
    while process_next_run(app.state.sessionmaker, app.state.settings, app.state.predictors):
        pass
