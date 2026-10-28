"""Shared FastAPI dependencies: database session, authentication, roles, audit context."""

import ipaddress
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.services.audit import AuditContext
from app.services.auth import Authenticated, authenticate


def app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(app_settings)]


def client_ip(request: Request) -> str | None:
    """The direct peer address, or None if it is not an IP (e.g. a Unix socket).

    X-Forwarded-For is deliberately not trusted: in the lab there is no trusted proxy, and
    the header is trivial to forge.
    """
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def request_id(request: Request) -> str | None:
    value = request.scope.get("state", {}).get("request_id")
    return str(value) if value else None


def current_auth(request: Request, db: DbSession, settings: AppSettings) -> Authenticated:
    return authenticate(db, settings, request.cookies.get(settings.session_cookie_name))


CurrentAuth = Annotated[Authenticated, Depends(current_auth)]


def current_user(auth: CurrentAuth) -> User:
    return auth.user


def require_admin(auth: CurrentAuth) -> User:
    if auth.user.role != "admin":
        raise AppError("forbidden", "Administrator role required", 403)
    return auth.user


# "Analyst or above": both roles may use analyst features.
AnalystUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


def audit_context(request: Request, user: AnalystUser) -> AuditContext:
    return AuditContext(actor=user, ip=client_ip(request), request_id=request_id(request))


Audit = Annotated[AuditContext, Depends(audit_context)]
