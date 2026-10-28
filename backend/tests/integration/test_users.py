import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit import AuditContext
from app.services.users import update_user
from tests.integration.conftest import CSRF, DEFAULT_PASSWORD, make_user


def test_admin_creates_and_lists_users(admin: TestClient, db: Session) -> None:
    response = admin.post(
        "/api/v1/users",
        json={"username": "Sita", "password": "a-long-password-1", "role": "analyst"},
    )
    assert response.status_code == 201
    assert response.json()["username"] == "sita"
    listing = admin.get("/api/v1/users").json()
    assert listing["total"] == 2 and {u["username"] for u in listing["items"]} == {"admin1", "sita"}
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "user.created")).all()[-1]
    assert entry.actor_label == "admin1" and entry.details == {"role": "analyst"}


def test_duplicate_username_conflicts(admin: TestClient) -> None:
    body = {"username": "admin1", "password": "a-long-password-1", "role": "analyst"}
    assert admin.post("/api/v1/users", json=body).status_code == 409


def test_weak_passwords_are_rejected(admin: TestClient) -> None:
    for password in ("short", "aaaaaaaaaaaaaaaa", "contains-ramesh-name"):
        response = admin.post(
            "/api/v1/users", json={"username": "ramesh", "password": password, "role": "analyst"}
        )
        assert response.status_code == 422, password
        assert response.json()["error"]["code"] == "weak_password"


def test_admin_cannot_lock_themselves_out(admin: TestClient, admin_user: User) -> None:
    for body in ({"role": "analyst"}, {"is_active": False}):
        response = admin.patch(f"/api/v1/users/{admin_user.id}", json=body)
        assert response.status_code == 409


def test_admin_may_demote_another_admin(admin: TestClient, db: Session) -> None:
    other = make_user(db, "admin2", "admin")
    assert admin.patch(f"/api/v1/users/{other.id}", json={"role": "analyst"}).status_code == 200


def test_last_active_admin_cannot_be_removed_even_by_the_system(
    admin_user: User, db: Session
) -> None:
    # Over the API the self-demotion guard fires first; this guard protects other callers
    # such as maintenance scripts.
    for change in ({"role": "analyst"}, {"is_active": False}):
        with pytest.raises(AppError) as excinfo:
            update_user(db, AuditContext.system("test"), admin_user.id, **change)  # type: ignore[arg-type]
        assert excinfo.value.status_code == 409


def test_password_reset_revokes_sessions_and_is_audited_without_the_password(
    app: FastAPI, admin: TestClient, analyst: TestClient, analyst_user: User, db: Session
) -> None:
    response = admin.patch(
        f"/api/v1/users/{analyst_user.id}", json={"password": "a-brand-new-pass-9"}
    )
    assert response.status_code == 200
    assert analyst.get("/api/v1/auth/me").status_code == 401
    with TestClient(app, headers=CSRF) as fresh:
        old = fresh.post(
            "/api/v1/auth/login", json={"username": "analyst1", "password": DEFAULT_PASSWORD}
        )
        assert old.status_code == 401
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "user.updated")).one()
    assert entry.details == {"password_reset": True}
    assert "a-brand-new-pass-9" not in str(entry.details)
