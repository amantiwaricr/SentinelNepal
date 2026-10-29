"""In-process notifications for WebSocket clients (alert created, collector status...).

Events are notifications only: REST stays the source of truth, and clients refetch on each
event, so a missed or dropped event never hides data. Worker threads publish; the event
loop delivers. Each connection has a small bounded queue; a slow client loses old events
rather than slowing anyone else down.
"""

import asyncio
import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

CLIENT_QUEUE_SIZE = 100


class EventHub:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._clients.discard(queue)

    def _deliver(self, event: dict[str, Any]) -> None:
        for queue in list(self._clients):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()  # drop the oldest for this slow client
            queue.put_nowait(event)

    def publish(self, event: dict[str, Any]) -> None:
        """Thread-safe. Does nothing until the app's event loop is bound (e.g. in tests)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._deliver, event)
        except RuntimeError:  # loop shutting down
            logger.debug("Event dropped: event loop is closed")
