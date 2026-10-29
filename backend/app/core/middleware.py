"""ASGI middleware: request correlation ids and baseline security headers."""

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
# Accept a caller-supplied id only if it is short and plain, so it cannot inject
# newlines or markup into logs.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
}
# API responses are JSON: they never need to run scripts, load resources or be framed, and
# they hold investigation data that should not be cached on shared machines.
API_ONLY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}
# The interactive API docs (development only) load Swagger UI scripts, so a strict CSP
# would break them.
DOCS_PREFIXES = ("/api/docs", "/api/redoc")

logger = logging.getLogger("app.request")


class RequestContextMiddleware:
    """Assigns a request id, adds security headers, and logs one line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = (
            incoming if incoming and _SAFE_REQUEST_ID.match(incoming) else str(uuid.uuid4())
        )
        token = request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        status_code = 500
        response_started = False
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                for key, value in SECURITY_HEADERS.items():
                    headers.setdefault(key, value)
                path = str(scope.get("path", ""))
                if path.startswith("/api/") and not path.startswith(DOCS_PREFIXES):
                    for key, value in API_ONLY_HEADERS.items():
                        headers.setdefault(key, value)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Handled here rather than by Starlette's outermost error middleware so the
            # 500 response still carries the request id in its body and headers.
            logger.exception("Unhandled exception")
            if response_started:
                raise
            response = error_response(500, "internal_error", "An unexpected error occurred")
            await response(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)",
                scope.get("method"),
                scope.get("path"),
                status_code,
                elapsed_ms,
            )
            request_id_var.reset(token)


CSRF_HEADER = b"x-requested-with"
CSRF_HEADER_VALUE = b"SentinelNepal"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CSRFHeaderMiddleware:
    """Require ``X-Requested-With: SentinelNepal`` on state-changing API requests.

    Browsers cannot add custom headers to cross-site form posts, and a cross-origin script
    that tries triggers a CORS preflight, which fails for origins not on the allowlist.
    Together with SameSite=Strict session cookies this blocks cross-site request forgery.
    """

    def __init__(self, app: ASGIApp, exempt_prefixes: tuple[str, ...] = ()) -> None:
        self.app = app
        self.exempt_prefixes = exempt_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope.get("method") in UNSAFE_METHODS
            and str(scope.get("path", "")).startswith("/api/")
            and not str(scope.get("path", "")).startswith(self.exempt_prefixes)
        ):
            value = dict(scope.get("headers", [])).get(CSRF_HEADER)
            if value != CSRF_HEADER_VALUE:
                response = error_response(
                    403,
                    "csrf_check_failed",
                    "State-changing requests must include the X-Requested-With header",
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Reject request bodies over a size limit before the application reads them.

    Without this, FastAPI reads a JSON body of any size into memory, and the multipart
    parser writes an oversized upload to a temporary file before the endpoint can refuse it.
    ``Content-Length`` is checked up front; bodies sent without it (chunked) are counted as
    they stream in and cut off at the limit.
    """

    def __init__(
        self, app: ASGIApp, default_limit: int, path_limits: dict[str, int] | None = None
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.path_limits = path_limits or {}

    def _limit(self, path: str) -> int:
        return self.path_limits.get(path.rstrip("/"), self.default_limit)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._limit(str(scope.get("path", "")))
        too_large = error_response(
            413, "payload_too_large", f"Request body exceeds the {limit} byte limit"
        )
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > limit):
            await too_large(scope, receive, send)
            return

        received = 0
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Answer 413 now and tell the application the client went away. (Raising
                    # here would be turned into a generic 400 by FastAPI's body parsing.)
                    rejected = True
                    await too_large(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not rejected:  # the 413 has already been sent
                await send(message)

        await self.app(scope, limited_receive, guarded_send)
