from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.session import get_engine
from app.main import create_app
from tests.conftest import make_settings


def _client(engine: Engine) -> TestClient:
    settings = make_settings()
    app = create_app(settings)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def test_ready_is_not_ready_before_migrations(engine: Engine) -> None:
    with _client(engine) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    components = response.json()["components"]
    assert components["database"]["status"] == "ok"
    assert components["migrations"]["status"] == "pending"


def test_ready_when_database_at_head(migrated_engine: Engine) -> None:
    with _client(migrated_engine) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["components"]["database"]["status"] == "ok"
    assert body["components"]["migrations"]["status"] == "ok"


def test_ready_reports_outdated_schema(migrated_engine: Engine, alembic_config: Config) -> None:
    command.downgrade(alembic_config, "base")
    command.stamp(alembic_config, "base")
    with _client(migrated_engine) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["components"]["migrations"]["status"] == "pending"
