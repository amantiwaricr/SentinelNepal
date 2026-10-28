from fastapi.testclient import TestClient
from sqlalchemy import create_engine

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


def test_app_starts_with_worker_enabled_while_database_is_down() -> None:
    # Regression: the worker used to query the database during startup, so an unavailable
    # database stopped the whole API from starting.
    settings = make_settings(
        database_url="postgresql+psycopg://nobody:pw@127.0.0.1:1/nodb",
        analysis_worker_enabled=True,
        analysis_poll_seconds=0.05,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.app.state.analysis_worker.alive  # type: ignore[attr-defined]
