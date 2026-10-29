"""WebSocket notifications for the dashboard (``/api/v1/events``).

Only signed-in users from an allowed origin may connect: browsers send the session cookie
with WebSocket handshakes, and the Origin check stops other sites from opening a socket
with that cookie (cross-site WebSocket hijacking). Messages are notifications only; the
dashboard refetches the data over REST.
"""

import asyncio
import contextlib
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import AppError
from app.services.auth import authenticate
from app.services.events import EventHub

router = APIRouter(tags=["events"])

SESSION_RECHECK_SECONDS = 60
POLICY_VIOLATION = 1008


def origin_allowed(websocket: WebSocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    if origin in settings.cors_origins:
        return True
    host = websocket.headers.get("host")
    return host is not None and origin in (f"http://{host}", f"https://{host}")


def _check_session(websocket: WebSocket) -> str:
    """The signed-in user's role; raises AppError if the session is not valid (any more)."""
    settings: Settings = websocket.app.state.settings
    with websocket.app.state.sessionmaker() as db:
        auth = authenticate(db, settings, websocket.cookies.get(settings.session_cookie_name))
        return auth.user.role


@router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    settings: Settings = websocket.app.state.settings
    if not origin_allowed(websocket, settings):
        await websocket.close(code=POLICY_VIOLATION)
        return
    try:
        role = await run_in_threadpool(_check_session, websocket)
    except AppError:
        await websocket.close(code=POLICY_VIOLATION)
        return
    await websocket.accept()
    hub: EventHub = websocket.app.state.events
    queue = hub.subscribe()

    async def forward() -> None:
        while True:
            try:
                event: dict[str, Any] = await asyncio.wait_for(
                    queue.get(), timeout=SESSION_RECHECK_SECONDS
                )
            except TimeoutError:
                # Sessions expire or are revoked; a long-lived socket must notice.
                try:
                    await run_in_threadpool(_check_session, websocket)
                except AppError:
                    await websocket.close(code=POLICY_VIOLATION)
                    return
                event = {"type": "ping"}
            await websocket.send_json(event)

    sender = asyncio.create_task(forward())
    try:
        await websocket.send_json({"type": "hello", "role": role})
        while True:
            await websocket.receive_text()  # clients send nothing useful; this detects close
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await sender
        hub.unsubscribe(queue)
