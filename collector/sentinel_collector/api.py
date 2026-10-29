"""Talks to the SentinelNepal ingest API (standard library HTTP only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class ApiError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class ApiClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self.base_url = base_url
        self._token = token
        self.timeout = timeout

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body, default=str).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 - URL scheme checked in Config
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                payload: dict[str, Any] = json.loads(response.read() or b"{}")
                return payload
        except urllib.error.HTTPError as exc:
            # 429 and 5xx are worth retrying; 4xx means the request itself is wrong.
            retryable = exc.code == 429 or exc.code >= 500
            raise ApiError(f"{path}: HTTP {exc.code}", retryable=retryable) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ApiError(
                f"{path}: API unreachable ({exc.__class__.__name__})", retryable=True
            ) from None
