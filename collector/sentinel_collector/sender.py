"""Buffers flow records and sends them in batches, retrying with backoff.

The buffer is bounded: if the API stays down long enough to fill it, the oldest records are
dropped and counted (reported in heartbeats), so the collector never runs out of memory.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sentinel_collector.api import ApiClient, ApiError

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 60.0


@dataclass
class SenderStats:
    sent: int = 0
    rejected_by_api: int = 0
    dropped_by_api: int = 0
    dropped_locally: int = 0
    send_failures: int = 0
    last_error: str | None = None


class Sender:
    def __init__(
        self,
        client: ApiClient,
        *,
        source: str = "live",
        batch_size: int = 200,
        buffer_limit: int = 20_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.source = source
        self.batch_size = batch_size
        self.buffer: deque[dict[str, Any]] = deque()
        self.buffer_limit = buffer_limit
        self.stats = SenderStats()
        self._clock = clock
        self._backoff = 0.0
        self._retry_at = 0.0

    def enqueue(self, records: list[dict[str, Any]]) -> None:
        self.buffer.extend(records)
        overflow = len(self.buffer) - self.buffer_limit
        for _ in range(max(0, overflow)):
            self.buffer.popleft()
        if overflow > 0:
            self.stats.dropped_locally += overflow
            logger.warning("Send buffer full: dropped %d oldest records", overflow)

    def flush(self) -> bool:
        """Send everything buffered. Returns False if it stopped early (API down)."""
        if self._clock() < self._retry_at:
            return False
        while self.buffer:
            batch = [self.buffer[i] for i in range(min(self.batch_size, len(self.buffer)))]
            try:
                result = self.client.post(
                    "/ingest/flows", {"source": self.source, "records": batch}
                )
            except ApiError as exc:
                self.stats.send_failures += 1
                self.stats.last_error = str(exc)
                if not exc.retryable:
                    # The batch itself was refused (e.g. 422); retrying would loop forever.
                    logger.error("Batch refused, discarding %d records: %s", len(batch), exc)
                    self._drop(len(batch))
                    continue
                self._backoff = min(MAX_BACKOFF_SECONDS, max(1.0, self._backoff * 2))
                self._retry_at = self._clock() + self._backoff
                logger.warning("Send failed (%s); retrying in %.0f s", exc, self._backoff)
                return False
            self._drop(len(batch))
            self._backoff = 0.0
            self.stats.sent += int(result.get("accepted", 0))
            self.stats.rejected_by_api += int(result.get("rejected", 0))
            self.stats.dropped_by_api += int(result.get("dropped", 0))
            for example in result.get("rejection_examples", [])[:1]:
                logger.warning("API rejected a record: %s", example)
        return True

    def _drop(self, count: int) -> None:
        for _ in range(count):
            self.buffer.popleft()
