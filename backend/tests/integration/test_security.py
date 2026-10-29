"""Phase 5 security tests: injection strings, stored script payloads, oversized input.

Payloads are classic test strings. They must be refused or treated as plain data, never
executed, and they must never cause a server error.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.model_version import ModelVersion
from app.models.user import User
from tests.integration.helpers import make_alert

SQLI = [
    "' OR '1'='1",
    "1; DROP TABLE alerts; --",
    "10.0.0.1' UNION SELECT password_hash FROM users --",
    '" OR ""="',
    "%27%20OR%201=1--",
]
XSS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "javascript:alert(1)",
    "{{constructor.constructor('alert(1)')()}}",
]


@pytest.mark.parametrize("payload", SQLI)
def test_injection_strings_in_filters_are_rejected_or_inert(
    analyst: TestClient,
    admin: TestClient,
    registered_model: ModelVersion,
    db: Session,
    payload: str,
) -> None:
    make_alert(db, registered_model)
    # Typed filters (IP, CIDR, enums, numbers) refuse the value outright.
    for path in (
        f"/api/v1/alerts?src_ip={payload}",
        f"/api/v1/alerts?cidr={payload}",
        f"/api/v1/alerts?category={payload}",
        f"/api/v1/alerts?sort={payload}",
        f"/api/v1/alerts?run_id={payload}",
        f"/api/v1/subnets?cidr={payload}",
        f"/api/v1/incidents?status={payload}",
    ):
        response = analyst.get(path)
        assert response.status_code == 422, path
    assert analyst.get(f"/api/v1/ips/{payload.replace('/', '%2F')}").status_code in (404, 422)
    # Free-text filters treat it as a literal value: no rows match, nothing breaks.
    for path in (
        f"/api/v1/audit-logs?actor={payload}",
        f"/api/v1/audit-logs?action={payload}",
        f"/api/v1/audit-logs?target_id={payload}",
    ):
        response = admin.get(path)
        assert response.status_code == 200, path
        assert response.json()["total"] == 0
    # The data is untouched.
    assert db.scalar(select(func.count()).select_from(Alert)) == 1
    assert db.execute(text("SELECT to_regclass('public.users')")).scalar() is not None


@pytest.mark.parametrize("payload", SQLI)
def test_injection_strings_at_login_get_the_generic_error(anon: TestClient, payload: str) -> None:
    response = anon.post("/api/v1/auth/login", json={"username": payload, "password": payload})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_script_payloads_are_stored_and_returned_as_plain_data(analyst: TestClient) -> None:
    """The API stores text verbatim and serves it as JSON; the frontend renders it as text
    (React escaping, no dangerouslySetInnerHTML, enforced by ESLint)."""
    for payload in XSS:
        incident = analyst.post(
            "/api/v1/incidents",
            json={"title": f"t {payload}", "description": payload},
        )
        assert incident.status_code == 201
        assert incident.headers["content-type"].startswith("application/json")
        incident_id = incident.json()["id"]
        note = analyst.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": payload})
        assert note.status_code == 201
        fetched = analyst.get(f"/api/v1/incidents/{incident_id}").json()
        assert fetched["title"] == f"t {payload}"
        assert fetched["description"] == payload
        notes = analyst.get(f"/api/v1/incidents/{incident_id}/notes").json()
        assert notes[0]["body"] == payload


def test_free_text_is_not_copied_into_the_audit_log(analyst: TestClient, db: Session) -> None:
    incident = analyst.post(
        "/api/v1/incidents", json={"title": "secret-ish title", "description": "<script>"}
    ).json()
    analyst.post(f"/api/v1/incidents/{incident['id']}/notes", json={"body": "note <b>text</b>"})
    details = " ".join(str(e.details) for e in db.scalars(select(AuditLog)).all())
    assert "<script>" not in details and "note <b>text</b>" not in details


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/v1/incidents", {"title": "x" * 201}),
        ("post", "/api/v1/incidents", {"title": "ok title", "description": "x" * 10_001}),
        ("post", "/api/v1/auth/login", {"username": "u" * 65, "password": "p"}),
        ("post", "/api/v1/auth/login", {"username": "u", "password": "p" * 257}),
        ("post", "/api/v1/incidents", {"title": "ok title", "alert_ids": list(range(1, 2000))}),
    ],
)
def test_oversized_fields_are_refused(
    analyst: TestClient, method: str, path: str, body: dict[str, object]
) -> None:
    response = getattr(analyst, method)(path, json=body)
    assert response.status_code == 422, response.text


def test_oversized_note_is_refused(analyst: TestClient) -> None:
    incident = analyst.post("/api/v1/incidents", json={"title": "ok title"}).json()
    response = analyst.post(
        f"/api/v1/incidents/{incident['id']}/notes", json={"body": "x" * 10_001}
    )
    assert response.status_code == 422


def test_oversized_firewall_reason_is_refused(admin: TestClient) -> None:
    response = admin.post(
        "/api/v1/firewall/requests",
        json={"target": "192.0.2.10", "duration_seconds": 600, "reason": "x" * 1001},
    )
    assert response.status_code == 422


def test_upload_over_the_limit_is_cut_off_while_streaming(app: FastAPI, analyst_user: User) -> None:
    """Without Content-Length the body limit middleware stops the stream at the limit, so
    the multipart parser never spools an oversized file to disk."""
    from app.main import create_app
    from tests.integration.conftest import logged_in_client

    settings = app.state.settings.model_copy(update={"max_upload_mb": 1})
    small_app = create_app(settings)
    client = logged_in_client(small_app, "analyst1")

    def body():  # type: ignore[no-untyped-def]
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="x.csv"\r\n\r\n'
        for _ in range(3 * 1024):
            yield b"a" * 1024

    response = client.post(
        "/api/v1/datasets/analyses",
        content=body(),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
