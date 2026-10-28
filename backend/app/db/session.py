"""Database engine and sessions.

Each application instance owns its engine (``app.state.engine``), created from its own
settings in ``create_app``. That keeps tests, the background worker, and the CLI on exactly
the database their settings name.
"""

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def engine_from_settings(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        # Fail fast when the database is unreachable instead of hanging health checks.
        connect_args={"connect_timeout": 5},
    )


def build_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed afterwards."""
    session: Session = request.app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def default_sessionmaker() -> sessionmaker[Session]:
    """For code running outside a request (the CLI), using the environment's settings."""
    return build_sessionmaker(engine_from_settings(get_settings()))
