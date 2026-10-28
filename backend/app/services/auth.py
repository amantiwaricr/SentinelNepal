"""Login, logout, and session validation."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    burn_verification_time,
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from app.core.time import utcnow
from app.models.session import UserSession
from app.models.user import User
from app.services import audit
from app.services.audit import AuditContext

# One message for every login failure, so callers cannot tell which usernames exist or are
# locked. The real reason goes to the audit log.
INVALID_CREDENTIALS = AppError("invalid_credentials", "Invalid username or password", 401)
SESSION_TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class Authenticated:
    user: User
    session: UserSession


def _fail(db: Session, ctx: AuditContext, reason: str, user: User | None = None) -> AppError:
    audit.record(
        db,
        AuditContext(actor=user, ip=ctx.ip, request_id=ctx.request_id, actor_type="anonymous"),
        "auth.login",
        target_type="user" if user else None,
        target_id=user.id if user else None,
        outcome="failure",
        details={"reason": reason},
    )
    db.commit()
    return INVALID_CREDENTIALS


def login(
    db: Session,
    settings: Settings,
    username: str,
    password: str,
    ctx: AuditContext,
    user_agent: str | None,
) -> tuple[User, str]:
    """Return the user and a new session token, or raise INVALID_CREDENTIALS."""
    now = utcnow()
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None:
        burn_verification_time(password)
        raise _fail(db, ctx, "unknown_user")
    if not user.is_active:
        burn_verification_time(password)
        raise _fail(db, ctx, "inactive", user)
    if user.locked_until is not None and user.locked_until > now:
        burn_verification_time(password)
        raise _fail(db, ctx, "locked", user)
    if not verify_password(user.password_hash, password):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.lockout_threshold:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
            audit.record(
                db,
                AuditContext.system("lockout"),
                "auth.account.locked",
                target_type="user",
                target_id=user.id,
                details={"minutes": settings.lockout_minutes},
            )
        raise _fail(db, ctx, "bad_password", user)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    token, token_hash = new_session_token()
    db.add(
        UserSession(
            token_hash=token_hash,
            user_id=user.id,
            last_seen_at=now,
            expires_at=now + timedelta(hours=settings.session_absolute_hours),
            ip_address=ctx.ip,
            user_agent=(user_agent or "")[:256] or None,
        )
    )
    audit.record(
        db,
        AuditContext(actor=user, ip=ctx.ip, request_id=ctx.request_id),
        "auth.login",
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    return user, token


def authenticate(db: Session, settings: Settings, token: str | None) -> Authenticated:
    """Validate a session cookie; raise 401 if it is missing, unknown, revoked, or expired."""
    if not token:
        raise AppError("not_authenticated", "Authentication required", 401)
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == hash_token(token))
    ).first()
    now = utcnow()
    if row is None:
        raise AppError("not_authenticated", "Authentication required", 401)
    session, user = row
    idle_limit = now - timedelta(minutes=settings.session_idle_minutes)
    if (
        session.revoked_at is not None
        or session.expires_at <= now
        or session.last_seen_at <= idle_limit
        or not user.is_active
    ):
        raise AppError("session_expired", "Session expired; please sign in again", 401)
    if now - session.last_seen_at > SESSION_TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return Authenticated(user=user, session=session)


def logout(db: Session, auth: Authenticated, ctx: AuditContext) -> None:
    auth.session.revoked_at = utcnow()
    audit.record(db, ctx, "auth.logout", target_type="user", target_id=auth.user.id)
    db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
