import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def test_audit_log_is_admin_only_and_filterable(
    admin: TestClient, analyst: TestClient, analyst_user: User
) -> None:
    assert analyst.get("/api/v1/audit-logs").status_code == 403
    analyst.post("/api/v1/incidents", json={"title": "Audit me"})
    everything = admin.get("/api/v1/audit-logs").json()
    assert everything["total"] >= 3  # user creations, logins, incident
    by_actor = admin.get("/api/v1/audit-logs?actor=analyst1").json()["items"]
    assert by_actor and all(e["actor_label"] == "analyst1" for e in by_actor)
    prefixed = admin.get("/api/v1/audit-logs?action=incident.").json()["items"]
    assert [e["action"] for e in prefixed] == ["incident.created"]
    assert admin.get("/api/v1/audit-logs?action=auth.login&outcome=success").json()["total"] == 2


def test_no_endpoint_modifies_audit_records(admin: TestClient) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert admin.request(method.upper(), "/api/v1/audit-logs").status_code == 405
        assert admin.request(method.upper(), "/api/v1/audit-logs/1").status_code == 404


@pytest.mark.parametrize(
    "statement",
    [
        update(AuditLog).values(action="tampered"),
        delete(AuditLog),
    ],
)
def test_database_rejects_audit_tampering(
    db: Session, analyst_user: User, statement: object
) -> None:
    assert db.scalar(select(AuditLog.id)) is not None
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(statement)  # type: ignore[call-overload]
    db.rollback()
