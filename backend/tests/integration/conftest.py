import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.services.health import ALEMBIC_INI

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
