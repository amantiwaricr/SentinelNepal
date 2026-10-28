import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from tests.integration.conftest import logged_in_client, make_user

VALID = {"target": "10.10.0.23", "duration_seconds": 900, "reason": "Repeated scans from host"}


@pytest.fixture
def second_admin(app: FastAPI, db: Session) -> TestClient:
    make_user(db, "admin2", "admin")
    return logged_in_client(app, "admin2")


def _create(client: TestClient, **overrides: object):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/firewall/requests", json={**VALID, **overrides})


def test_two_person_approval_with_typed_confirmation(
    admin: TestClient, second_admin: TestClient, db: Session
) -> None:
    created = _create(admin)
    assert created.status_code == 201
    request = created.json()
    assert request["target"] == "10.10.0.23/32" and request["status"] == "pending"
    rid = request["id"]

    self_approve = admin.post(
        f"/api/v1/firewall/requests/{rid}/approve", json={"confirm_target": "10.10.0.23/32"}
    )
    assert self_approve.status_code == 403
    assert self_approve.json()["error"]["code"] == "self_approval"

    mismatch = second_admin.post(
        f"/api/v1/firewall/requests/{rid}/approve", json={"confirm_target": "10.10.0.24"}
    )
    assert (
        mismatch.status_code == 422 and mismatch.json()["error"]["code"] == "confirmation_mismatch"
    )

    approved = second_admin.post(
        f"/api/v1/firewall/requests/{rid}/approve",
        json={"confirm_target": "10.10.0.23", "note": "Confirmed with incident lead"},
    ).json()
    assert approved["status"] == "approved" and approved["approved_by"] is not None
    # Nothing is applied in Phase 3, and the API never says otherwise.
    assert approved["applied"] is False and approved["results"] == []
    assert approved["expires_at"] is None

    actions = [
        (a.action, a.outcome, a.actor_label)
        for a in db.scalars(select(AuditLog).order_by(AuditLog.id))
        if a.action.startswith("firewall")
    ]
    assert actions == [
        ("firewall.request.created", "success", "admin1"),
        ("firewall.request.approve", "denied", "admin1"),
        ("firewall.request.approved", "success", "admin2"),
    ]
    approval = db.scalars(
        select(AuditLog).where(AuditLog.action == "firewall.request.approved")
    ).one()
    assert "nothing has been applied" in approval.details["execution"]


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("not-an-ip", "invalid_target"),
        ("10.0.0.5/24", "invalid_target"),  # host bits set
        ("127.0.0.1", "protected_target"),
        ("::1", "protected_target"),
        ("169.254.10.1", "protected_target"),
        ("224.0.0.1", "protected_target"),
        ("0.0.0.0", "protected_target"),  # noqa: S104 (a target to refuse, not a bind)
        ("255.255.255.255", "protected_target"),
        ("10.0.0.0/8", "cidr_too_broad"),
        ("2001:db8::/32", "cidr_too_broad"),
        ("192.168.56.10", "protected_target"),  # inside the configured management network
    ],
)
def test_unsafe_targets_are_refused(
    app: FastAPI, admin: TestClient, target: str, code: str
) -> None:
    app.state.settings.firewall_protected_networks = ["192.168.56.0/24"]
    response = _create(admin, target=target)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code


def test_valid_ipv6_and_subnet_targets(admin: TestClient) -> None:
    assert _create(admin, target="10.10.0.0/24").json()["target"] == "10.10.0.0/24"
    assert _create(admin, target="2001:db8::5").json()["target"] == "2001:db8::5/128"


def test_duplicate_open_requests_conflict(admin: TestClient) -> None:
    assert _create(admin).status_code == 201
    duplicate = _create(admin, target="10.10.0.23/32")
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "duplicate_request"


def test_duration_and_reason_limits(admin: TestClient) -> None:
    assert _create(admin, duration_seconds=7200).json()["error"]["code"] == "duration_too_long"
    assert _create(admin, duration_seconds=30).status_code == 422
    assert _create(admin, reason="short").status_code == 422


def test_analysts_cannot_request_or_decide(
    app: FastAPI, analyst: TestClient, admin: TestClient
) -> None:
    assert _create(analyst).status_code == 403
    rid = _create(admin).json()["id"]
    for action, body in (
        ("approve", {"confirm_target": "10.10.0.23"}),
        ("reject", {"note": "no"}),
        ("revoke", {}),
    ):
        assert (
            analyst.post(f"/api/v1/firewall/requests/{rid}/{action}", json=body).status_code == 403
        )
    assert analyst.get("/api/v1/firewall/requests").json()["total"] == 1  # viewing is allowed
    app.state.settings.firewall_analysts_may_request = True
    assert _create(analyst, target="10.10.0.99").status_code == 201


def test_self_approval_can_be_enabled_for_solo_demos(app: FastAPI, admin: TestClient) -> None:
    app.state.settings.firewall_allow_self_approval = True
    rid = _create(admin).json()["id"]
    response = admin.post(
        f"/api/v1/firewall/requests/{rid}/approve", json={"confirm_target": "10.10.0.23"}
    )
    assert response.json()["status"] == "approved"


def test_reject_and_revoke_lifecycle(admin: TestClient, second_admin: TestClient) -> None:
    rid = _create(admin).json()["id"]
    assert admin.post(f"/api/v1/firewall/requests/{rid}/revoke", json={}).status_code == 409
    rejected = second_admin.post(
        f"/api/v1/firewall/requests/{rid}/reject", json={"note": "Insufficient evidence"}
    )
    assert rejected.json()["status"] == "rejected"
    # The target is free again for a new request.
    rid2 = _create(admin).json()["id"]
    second_admin.post(
        f"/api/v1/firewall/requests/{rid2}/approve", json={"confirm_target": "10.10.0.23"}
    )
    first = admin.post(f"/api/v1/firewall/requests/{rid2}/revoke", json={"note": "Scan stopped"})
    assert first.json()["status"] == "revoked" and first.json()["revoked_at"] is not None
    again = admin.post(f"/api/v1/firewall/requests/{rid2}/revoke", json={})
    assert again.status_code == 200 and again.json()["revoked_at"] == first.json()["revoked_at"]


def test_status_reports_helper_not_configured(admin: TestClient, analyst: TestClient) -> None:
    status = admin.get("/api/v1/firewall/status").json()
    assert status["helper"] == "not_configured" and "nothing is applied" in status["detail"]
    assert analyst.get("/api/v1/firewall/status").status_code == 403
