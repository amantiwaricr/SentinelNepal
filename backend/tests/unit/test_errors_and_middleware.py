import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import AppError
from app.main import create_app
from tests.conftest import make_settings


class _Payload(BaseModel):
    password: str
    count: int


def _app_with_test_routes() -> FastAPI:
    app = create_app(make_settings())

    @app.post("/test/validate")
    def validate(payload: _Payload) -> dict[str, int]:
        return {"count": payload.count}

    @app.get("/test/app-error")
    def app_error() -> None:
        raise AppError("conflict", "Already exists", status_code=409, details={"field": "name"})

    @app.get("/test/crash")
    def crash() -> None:
        raise RuntimeError("database password is hunter2")

    return app


def _assert_envelope(body: dict[str, object], code: str) -> dict[str, object]:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == code
    assert error["request_id"]
    return error


def test_unknown_route_returns_not_found_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    error = _assert_envelope(response.json(), "not_found")
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_wrong_method_returns_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/health/live", headers={"X-Requested-With": "SentinelNepal"})
    assert response.status_code == 405
    _assert_envelope(response.json(), "method_not_allowed")


def test_validation_error_lists_fields_without_echoing_input() -> None:
    with TestClient(_app_with_test_routes()) as client:
        response = client.post(
            "/test/validate",
            json={"password": "s3cret-value", "count": "not-a-number"},
            headers={"X-Requested-With": "SentinelNepal"},
        )
    assert response.status_code == 422
    error = _assert_envelope(response.json(), "validation_error")
    details = error["details"]
    assert isinstance(details, list)
    assert any(item["loc"] == ["body", "count"] for item in details)
    assert "s3cret-value" not in response.text
    assert "not-a-number" not in response.text


def test_app_error_is_mapped_to_envelope() -> None:
    with TestClient(_app_with_test_routes()) as client:
        response = client.get("/test/app-error")
    assert response.status_code == 409
    error = _assert_envelope(response.json(), "conflict")
    assert error["message"] == "Already exists"
    assert error["details"] == {"field": "name"}


def test_unhandled_exception_returns_generic_500_with_request_id() -> None:
    with TestClient(_app_with_test_routes()) as client:
        response = client.get("/test/crash")
    assert response.status_code == 500
    error = _assert_envelope(response.json(), "internal_error")
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text


def test_request_id_is_generated_when_absent(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    uuid.UUID(response.headers["X-Request-ID"])


def test_safe_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "abc-12345-def"})
    assert response.headers["X-Request-ID"] == "abc-12345-def"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "bad id<script>"})
    assert response.headers["X-Request-ID"] != "bad id<script>"
    uuid.UUID(response.headers["X-Request-ID"])


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert (
        response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["Cache-Control"] == "no-store"


def test_docs_are_not_given_the_strict_api_csp(client: TestClient) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"


def test_oversized_json_body_is_refused_before_parsing(client: TestClient) -> None:
    body = b'{"username": "a", "password": "' + b"x" * (70 * 1024) + b'"}'
    response = client.post(
        "/api/v1/auth/login",
        content=body,
        headers={"Content-Type": "application/json", "X-Requested-With": "SentinelNepal"},
    )
    assert response.status_code == 413
    _assert_envelope(response.json(), "payload_too_large")


def test_oversized_body_without_content_length_is_cut_off(client: TestClient) -> None:
    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(80):
            yield b"x" * 1024

    response = client.post(
        "/api/v1/auth/login",
        content=chunks(),
        headers={"Content-Type": "application/json", "X-Requested-With": "SentinelNepal"},
    )
    assert response.status_code == 413


def test_invalid_content_length_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={"Content-Length": "abc", "X-Requested-With": "SentinelNepal"},
    )
    assert response.status_code in (400, 413)


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_ignores_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_state_changing_api_requests_need_the_csrf_header(client: TestClient, method: str) -> None:
    response = client.request(method.upper(), "/api/v1/auth/logout")
    assert response.status_code == 403
    _assert_envelope(response.json(), "csrf_check_failed")


def test_csrf_header_must_have_the_exact_value(client: TestClient) -> None:
    response = client.post("/api/v1/auth/logout", headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 403


def test_safe_methods_do_not_need_the_csrf_header(client: TestClient) -> None:
    assert client.get("/api/v1/health/live").status_code == 200


@pytest.mark.parametrize(
    ("host", "expected"),
    [("10.0.0.5", "10.0.0.5"), ("2001:DB8::1", "2001:db8::1"), ("testclient", None), (None, None)],
)
def test_client_ip_only_returns_valid_addresses(host: str | None, expected: str | None) -> None:
    from types import SimpleNamespace

    from app.api.deps import client_ip

    request = SimpleNamespace(client=SimpleNamespace(host=host) if host else None)
    assert client_ip(request) == expected  # type: ignore[arg-type]
