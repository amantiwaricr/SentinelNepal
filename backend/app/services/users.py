"""User administration. Guards prevent administrators from locking everyone out."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, password_problems
from app.models.user import User
from app.services import audit
from app.services.audit import AuditContext
from app.services.auth import revoke_all_sessions


def _check_password(password: str, username: str) -> None:
    problems = password_problems(password, username)
    if problems:
        raise AppError("weak_password", "Password " + "; ".join(problems), 422)


def create_user(db: Session, ctx: AuditContext, username: str, password: str, role: str) -> User:
    username = username.strip().lower()
    _check_password(password, username)
    user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("conflict", "Username already exists", 409) from None
    audit.record(
        db, ctx, "user.created", target_type="user", target_id=user.id, details={"role": role}
    )
    db.commit()
    return user


def _active_admins(db: Session) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active)
        )
        or 0
    )


def update_user(
    db: Session,
    ctx: AuditContext,
    user_id: int,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("not_found", "User not found", 404)
    actor = ctx.actor
    changes: dict[str, object] = {}

    removes_admin = (
        user.role == "admin"
        and user.is_active
        and ((role is not None and role != "admin") or is_active is False)
    )
    if removes_admin and actor is not None and actor.id == user.id:
        raise AppError("conflict", "You cannot demote or deactivate your own account", 409)
    if removes_admin and _active_admins(db) <= 1:
        raise AppError("conflict", "At least one active administrator must remain", 409)

    if role is not None and role != user.role:
        changes["role"] = {"from": user.role, "to": role}
        user.role = role
    if is_active is not None and is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": is_active}
        user.is_active = is_active
        if not is_active:
            revoke_all_sessions(db, user.id)
    if password is not None:
        _check_password(password, user.username)
        user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        revoke_all_sessions(db, user.id)
        changes["password_reset"] = True  # never the password itself

    if changes:
        audit.record(
            db, ctx, "user.updated", target_type="user", target_id=user.id, details=changes
        )
    db.commit()
    return user
