from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import create_app
from tests.conftest import make_settings


def test_live_reports_service_and_version(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "SentinelNepal"
    assert body["version"]


def test_ready_reports_unreachable_database_without_leaking_details() -> None:
    settings = make_settings(database_url="postgresql+psycopg://nobody:secret-pw@127.0.0.1:1/nodb")
    app = create_app(settings)
    unreachable = create_engine(settings.sqlalchemy_url, connect_args={"connect_timeout": 2})
    app.dependency_overrides[get_engine] = lambda: unreachable
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["components"]["database"]["status"] == "unavailable"
    assert body["components"]["migrations"]["status"] == "unknown"
    # Neither credentials nor host details may appear in the public response.
    assert "secret-pw" not in response.text
    assert "127.0.0.1" not in response.text
