from fastapi import APIRouter, Request, Response

from app.api.deps import (
    AppSettings,
    Audit,
    CurrentAuth,
    DbSession,
    client_ip,
    request_id,
)
from app.core.errors import AppError
from app.schemas.users import LoginIn, UserOut
from app.services import audit, auth
from app.services.audit import AuditContext

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(
    body: LoginIn, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    ip = client_ip(request)
    ctx = AuditContext.anonymous(ip, request_id(request))
    limiter = request.app.state.login_limiter
    key = f"login:{ip}"
    if not limiter.allow(key):
        audit.record(db, ctx, "auth.login", outcome="denied", details={"reason": "rate_limited"})
        db.commit()
        raise AppError(
            "rate_limited",
            "Too many login attempts; try again later",
            429,
            details={"retry_after_seconds": limiter.retry_after(key)},
        )
    user, token = auth.login(
        db, settings, body.username, body.password, ctx, request.headers.get("user-agent")
    )
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_absolute_hours * 3600,
        path="/api",
        httponly=True,  # not readable by JavaScript, so XSS cannot steal it
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(
    current: CurrentAuth, ctx: Audit, db: DbSession, settings: AppSettings, response: Response
) -> Response:
    auth.logout(db, current, ctx)
    response.delete_cookie(settings.session_cookie_name, path="/api")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(current: CurrentAuth) -> UserOut:
    return UserOut.model_validate(current.user)
