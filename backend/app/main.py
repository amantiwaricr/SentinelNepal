"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import APP_NAME, APP_VERSION, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import CSRFHeaderMiddleware, RequestContextMiddleware
from app.core.rate_limit import SlidingWindowLimiter
from app.db.session import build_sessionmaker, engine_from_settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("%s %s starting (environment=%s)", APP_NAME, APP_VERSION, settings.environment)
        yield
        logger.info("%s shutting down", APP_NAME)
        app.state.engine.dispose()

    app = FastAPI(
        title=f"{APP_NAME} API",
        version=APP_VERSION,
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(CSRFHeaderMiddleware)
    # Added last so it is the outermost middleware and sees every response.
    app.add_middleware(RequestContextMiddleware)

    app.state.settings = settings
    app.state.engine = engine_from_settings(settings)  # connects lazily
    app.state.sessionmaker = build_sessionmaker(app.state.engine)
    app.state.login_limiter = SlidingWindowLimiter(
        settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds
    )

    register_exception_handlers(app)
    app.include_router(api_router)
    return app
