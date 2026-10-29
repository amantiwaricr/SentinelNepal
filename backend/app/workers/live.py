"""Background thread that scores ingested live and replayed flows."""

import logging
import threading

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.services.events import EventHub
from app.services.live.ingest import IngestQueue, RecentFlows, process_batch, publish_batch_events
from app.services.ml_service import PredictorCache

logger = logging.getLogger(__name__)


class LiveWorker:
    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: Settings,
        predictors: PredictorCache,
        ingest: IngestQueue,
        hub: EventHub,
        recent: RecentFlows,
    ) -> None:
        self._factory = factory
        self._settings = settings
        self._predictors = predictors
        self._ingest = ingest
        self._hub = hub
        self._recent = recent
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="live-worker", daemon=True)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 10) -> None:
        self._stop.set()
        self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            batch = self._ingest.take(timeout=1.0)
            if batch is None:
                continue
            try:
                with self._factory() as db:
                    result = process_batch(db, self._settings, self._predictors, batch)
                publish_batch_events(self._hub, self._recent, batch, result)
            except Exception:  # one bad batch must not stop live scoring
                logger.exception("Live batch from collector %s failed", batch.collector_id)
