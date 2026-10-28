"""Background thread that analyses queued uploads one at a time."""

import logging
import threading

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.services.analyses import process_next_run, recover_interrupted
from app.services.ml_service import PredictorCache

logger = logging.getLogger(__name__)


class AnalysisWorker:
    """Never touches the database during ``start()``, so the API starts (and reports "not
    ready") even when PostgreSQL is down; the thread retries until it can connect."""

    def __init__(
        self, factory: sessionmaker[Session], settings: Settings, predictors: PredictorCache
    ) -> None:
        self._factory = factory
        self._settings = settings
        self._predictors = predictors
        self._stop = threading.Event()
        self._recovered = False
        self._thread = threading.Thread(target=self._run, name="analysis-worker", daemon=True)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 10) -> None:
        self._stop.set()
        self._thread.join(timeout)

    def _iteration(self) -> bool:
        if not self._recovered:
            recovered = recover_interrupted(self._factory)
            if recovered:
                logger.warning("Marked %d interrupted analysis run(s) as failed", recovered)
            self._recovered = True
        return process_next_run(self._factory, self._settings, self._predictors)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                busy = self._iteration()
            except Exception:  # keep the worker alive; runs record their own failures
                logger.exception("Analysis worker iteration failed; retrying")
                busy = False
            if not busy:
                self._stop.wait(self._settings.analysis_poll_seconds)
