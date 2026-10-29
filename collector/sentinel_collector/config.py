"""Collector settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


def _number(name: str, default: float, *, minimum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number") from None
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class Config:
    api_url: str
    token: str
    capture_dir: Path
    state_file: Path
    batch_size: int = 200
    buffer_limit: int = 20_000
    heartbeat_seconds: float = 10.0
    poll_seconds: float = 2.0
    flow_idle_timeout: float = 30.0
    request_timeout: float = 10.0

    @classmethod
    def from_env(cls) -> Config:
        token = os.environ.get("COLLECTOR_TOKEN", "").strip()
        if not token:
            raise ConfigError(
                "COLLECTOR_TOKEN is not set. Create a collector with "
                "`python -m app.cli create-collector --name lab-sensor` and put its token in .env."
            )
        api_url = os.environ.get("SENTINEL_API_URL", "http://backend:8000/api/v1").rstrip("/")
        if not api_url.startswith(("http://", "https://")):
            raise ConfigError("SENTINEL_API_URL must start with http:// or https://")
        capture_dir = Path(os.environ.get("CAPTURE_DIR", "/captures"))
        return cls(
            api_url=api_url,
            token=token,
            capture_dir=capture_dir,
            state_file=Path(os.environ.get("STATE_FILE", "/tmp/sentinel-collector.state")),  # noqa: S108 - container-private tmp
            batch_size=int(_number("BATCH_SIZE", 200, minimum=1)),
            buffer_limit=int(_number("BUFFER_LIMIT", 20_000, minimum=100)),
            heartbeat_seconds=_number("HEARTBEAT_SECONDS", 10, minimum=1),
            poll_seconds=_number("POLL_SECONDS", 2, minimum=0.2),
            flow_idle_timeout=_number("FLOW_IDLE_TIMEOUT", 30, minimum=1),
        )
