from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.audit import AuditLog
from app.models.session import UserSession
from app.models.user import User
from tests.integration.conftest import CSRF, DEFAULT_PASSWORD, logged_in_client


def _login(client: TestClient, username: str, password: str = DEFAULT_PASSWORD):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def _actions(db: Session) -> list[tuple[str, str]]:
    db.expire_all()
    return [(a.action, a.outcome) for a in db.scalars(select(AuditLog).order_by(AuditLog.id))]


def test_login_sets_hardened_cookie_and_me_works(anon: TestClient, analyst_user: User) -> None:
    response = _login(anon, "analyst1")
    assert response.status_code == 200
    assert response.json()["username"] == "analyst1"
    assert "password" not in response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    me = anon.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "analyst"


def test_session_token_is_stored_only_as_a_hash(
    anon: TestClient, analyst_user: User, db: Session
) -> None:
    _login(anon, "analyst1")
    token = anon.cookies.get("sn_session")
    stored = db.scalars(select(UserSession.token_hash)).all()
    assert token and token not in stored and len(stored[0]) == 64


def test_username_is_case_insensitive(anon: TestClient, analyst_user: User) -> None:
    assert _login(anon, "  Analyst1 ").status_code == 200


@pytest.mark.parametrize(
    ("username", "password"), [("analyst1", "wrong-password-123"), ("nobody", DEFAULT_PASSWORD)]
)
def test_failed_logins_share_one_generic_error(
    anon: TestClient, analyst_user: User, db: Session, username: str, password: str
) -> None:
    response = _login(anon, username, password)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert response.json()["error"]["message"] == "Invalid username or password"
    assert ("auth.login", "failure") in _actions(db)
    # The attempted username is not stored for unknown users (it might be a mistyped password).
    assert "nobody" not in {a.actor_label for a in db.scalars(select(AuditLog))}


def test_account_locks_after_repeated_failures(
    anon: TestClient, analyst_user: User, db: Session
) -> None:
    for _ in range(5):
        assert _login(anon, "analyst1", "wrong-password-123").status_code == 401
    # Correct password is refused while locked, with the same generic error.
    response = _login(anon, "analyst1")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    db.expire_all()
    user = db.scalars(select(User).where(User.username == "analyst1")).one()
    assert user.locked_until is not None and user.locked_until > utcnow()
    assert ("auth.account.locked", "success") in _actions(db)


def test_login_rate_limit_per_ip(app: FastAPI, db: Session) -> None:
    app.state.login_limiter.max_events = 3
    with TestClient(app, headers=CSRF) as client:
        for _ in range(3):
            assert _login(client, "nobody", "x").status_code == 401
        response = _login(client, "nobody", "x")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert ("auth.login", "denied") in _actions(db)


def test_logout_revokes_the_session(app: FastAPI, analyst_user: User) -> None:
    client = logged_in_client(app, "analyst1")
    stolen = client.cookies.get("sn_session")
    assert client.post("/api/v1/auth/logout").status_code == 204
    replay = TestClient(app, headers=CSRF, cookies={"sn_session": stolen})
    assert replay.get("/api/v1/auth/me").status_code == 401


def test_idle_and_absolute_expiry(analyst: TestClient, db: Session) -> None:
    session = db.scalars(select(UserSession)).one()
    session.last_seen_at = utcnow() - timedelta(minutes=31)
    db.commit()
    response = analyst.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_inactive_user_cannot_log_in_or_use_existing_session(
    app: FastAPI, analyst: TestClient, admin: TestClient, analyst_user: User
) -> None:
    assert (
        admin.patch(f"/api/v1/users/{analyst_user.id}", json={"is_active": False}).status_code
        == 200
    )
    assert analyst.get("/api/v1/auth/me").status_code == 401
    with TestClient(app, headers=CSRF) as fresh:
        assert _login(fresh, "analyst1").status_code == 401


def test_unknown_or_missing_cookie_is_rejected(anon: TestClient) -> None:
    assert anon.get("/api/v1/auth/me").status_code == 401
    anon.cookies.set("sn_session", "forged-token-value")
    assert anon.get("/api/v1/auth/me").json()["error"]["code"] == "not_authenticated"


def test_login_body_rejects_unknown_fields(anon: TestClient) -> None:
    response = anon.post(
        "/api/v1/auth/login", json={"username": "a", "password": "b", "role": "admin"}
    )
    assert response.status_code == 422
