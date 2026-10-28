"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

APP_NAME = "SentinelNepal"
APP_VERSION = "0.1.0"

# One .env at the repository root serves Docker Compose and native runs. Real environment
# variables always win over the file; inside the container the file is simply absent.
REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
# Values from .env.example that must never be used outside development.
PLACEHOLDER_SECRETS = frozenset({"", "change-me"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # Either a full DATABASE_URL, or the POSTGRES_* parts below. Building the URL from parts
    # with URL.create() means passwords containing '@', '/' or ':' need no manual escaping.
    database_url: SecretStr | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "sentinel"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "sentinelnepal"

    # Comma-separated in the environment, e.g. "http://localhost:5173,http://127.0.0.1:5173".
    # NoDecode stops pydantic-settings from trying to parse the value as JSON first.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard(cls, value: list[str]) -> list[str]:
        # Credentials (session cookies) will be sent cross-origin in later phases, and a
        # wildcard origin combined with credentials would let any website call the API.
        if "*" in value:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed")
        return value

    # --- Sessions and login protection ---
    session_cookie_name: str = "sn_session"
    session_idle_minutes: int = Field(default=30, ge=5, le=24 * 60)
    session_absolute_hours: int = Field(default=12, ge=1, le=7 * 24)
    # None = Secure only in production, so plain-HTTP development on localhost still works.
    session_cookie_secure: bool | None = None
    login_rate_limit_attempts: int = Field(default=10, ge=1)
    login_rate_limit_window_seconds: int = Field(default=300, ge=1)
    lockout_threshold: int = Field(default=5, ge=1)
    lockout_minutes: int = Field(default=15, ge=1)

    # --- Dataset analysis ---
    upload_dir: Path = BACKEND_ROOT / "uploads"
    max_upload_mb: int = Field(default=200, ge=1, le=2048)
    # Artifacts are produced by `sentinel-ml train` and registered with `python -m app.cli`.
    model_artifacts_dir: Path = BACKEND_ROOT.parent / "ml" / "artifacts"
    dataset_model_profile: str = "full"
    analysis_worker_enabled: bool = True
    analysis_poll_seconds: float = Field(default=2.0, gt=0)
    # Safety cap: beyond this, further alerts in one run are counted but not stored.
    max_alerts_per_run: int = Field(default=100_000, ge=1)

    # --- Firewall requests (execution arrives in Phase 7) ---
    firewall_allow_self_approval: bool = False
    firewall_analysts_may_request: bool = False
    firewall_max_duration_seconds: int = Field(default=3600, ge=60, le=86_400)
    # Comma-separated networks that may never be blocked, e.g. the lab management subnet.
    firewall_protected_networks: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("firewall_protected_networks", mode="before")
    @classmethod
    def _split_networks(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _refuse_placeholder_secrets(self) -> "Settings":
        # A production deployment must never run with the example password.
        if (
            self.environment == "production"
            and self.database_url is None
            and self.postgres_password.get_secret_value() in PLACEHOLDER_SECRETS
        ):
            raise ValueError("POSTGRES_PASSWORD is empty or a placeholder in production")
        return self

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.environment == "production"

    @property
    def sqlalchemy_url(self) -> URL:
        if self.database_url is not None:
            return make_url(self.database_url.get_secret_value())
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value() or None,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
