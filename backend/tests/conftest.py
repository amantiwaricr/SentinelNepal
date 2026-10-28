from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_settings(**overrides: object) -> Settings:
    # _env_file=None keeps a developer's local .env from leaking into tests.
    values: dict[str, object] = {
        "environment": "test",
        "log_format": "text",
        "cors_origins": ["http://localhost:5173"],
        # Tests drive analysis runs explicitly instead of through the background thread.
        "analysis_worker_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
