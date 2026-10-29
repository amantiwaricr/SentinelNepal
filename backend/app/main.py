"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v1.datasets import MULTIPART_OVERHEAD, UPLOAD_PATH
from app.core.config import APP_NAME, APP_VERSION, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    CSRFHeaderMiddleware,
    RequestContextMiddleware,
)
from app.core.rate_limit import SlidingWindowLimiter
from app.db.session import build_sessionmaker, engine_from_settings
from app.services.events import EventHub
from app.services.live.ingest import IngestQueue, RecentFlows
from app.services.ml_service import PredictorCache
from app.workers.analysis import AnalysisWorker
from app.workers.live import LiveWorker

logger = logging.getLogger(__name__)

# The largest legitimate JSON body is a 10,000-character note or description (up to 40 KB
# of UTF-8); 64 KiB leaves room for that and refuses anything far larger.
MAX_JSON_BODY_BYTES = 64 * 1024
# Collector batches hold up to 500 flow records of ~1.5 KB each.
MAX_INGEST_BODY_BYTES = 2 * 1024 * 1024
INGEST_PREFIX = "/api/v1/ingest/"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("%s %s starting (environment=%s)", APP_NAME, APP_VERSION, settings.environment)
        app.state.events.bind(asyncio.get_running_loop())
        if settings.live_worker_enabled:
            app.state.live_worker = LiveWorker(
                app.state.sessionmaker,
                settings,
                app.state.predictors,
                app.state.ingest_queue,
                app.state.events,
                app.state.recent_flows,
            )
            app.state.live_worker.start()
        if settings.analysis_worker_enabled:
            app.state.analysis_worker = AnalysisWorker(
                app.state.sessionmaker, settings, app.state.predictors
            )
            app.state.analysis_worker.start()
        yield
        logger.info("%s shutting down", APP_NAME)
        if app.state.analysis_worker is not None:
            app.state.analysis_worker.stop()
        if app.state.live_worker is not None:
            app.state.live_worker.stop()
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
    # Collectors authenticate with a bearer token, not a cookie, so CSRF does not apply.
    app.add_middleware(CSRFHeaderMiddleware, exempt_prefixes=(INGEST_PREFIX,))
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=MAX_JSON_BODY_BYTES,
        path_limits={
            UPLOAD_PATH: settings.max_upload_mb * 1024 * 1024 + MULTIPART_OVERHEAD,
            INGEST_PREFIX + "flows": MAX_INGEST_BODY_BYTES,
        },
    )
    # Added last so it is the outermost middleware and sees every response.
    app.add_middleware(RequestContextMiddleware)

    app.state.settings = settings
    app.state.engine = engine_from_settings(settings)  # connects lazily
    app.state.sessionmaker = build_sessionmaker(app.state.engine)
    app.state.predictors = PredictorCache(settings)
    app.state.analysis_worker = None  # started in lifespan when enabled
    app.state.login_limiter = SlidingWindowLimiter(
        settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds
    )
    # Live monitoring: bounded ingest queue, latest flows, notifications, failed-token limit.
    app.state.ingest_queue = IngestQueue(settings.ingest_queue_batches)
    app.state.recent_flows = RecentFlows()
    app.state.events = EventHub()
    app.state.live_worker = None  # started in lifespan when enabled
    app.state.ingest_failure_limiter = SlidingWindowLimiter(20, 60)

    register_exception_handlers(app)
    app.include_router(api_router)
    return app
