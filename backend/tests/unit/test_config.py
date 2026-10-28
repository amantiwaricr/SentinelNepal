from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.conftest import make_settings


def test_url_built_from_parts_escapes_special_characters() -> None:
    settings = make_settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_user="sentinel",
        postgres_password="p@ss/w:rd",
        postgres_db="sentinelnepal",
    )
    url = settings.sqlalchemy_url
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db"
    assert url.password == "p@ss/w:rd"
    assert url.database == "sentinelnepal"


def test_database_url_takes_precedence_over_parts() -> None:
    settings = make_settings(
        database_url="postgresql+psycopg://u:p@example:6543/other", postgres_host="db"
    )
    assert settings.sqlalchemy_url.host == "example"
    assert settings.sqlalchemy_url.port == 6543


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    settings = make_settings(cors_origins="http://a.test, http://b.test,")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_wildcard_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(cors_origins="*")


def test_docs_disabled_in_production() -> None:
    assert make_settings(environment="production").docs_enabled is False
    assert make_settings(environment="development").docs_enabled is True


def test_secret_not_shown_in_repr() -> None:
    settings = make_settings(postgres_password="topsecret")
    assert "topsecret" not in repr(settings)


def test_comma_separated_cors_origins_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: list-typed settings must accept the documented comma-separated format
    # from real environment variables, not only from Python keyword arguments.
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_read_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CORS_ORIGINS=http://localhost:5173\nPOSTGRES_HOST=dbhost\nPOSTGRES_PORT=5433\n"
    )
    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]
    assert settings.cors_origins == ["http://localhost:5173"]
    assert settings.sqlalchemy_url.host == "dbhost"
    assert settings.sqlalchemy_url.port == 5433


def test_environment_variables_override_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_HOST=from-file\n")
    monkeypatch.setenv("POSTGRES_HOST", "from-env")
    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]
    assert settings.sqlalchemy_url.host == "from-env"
