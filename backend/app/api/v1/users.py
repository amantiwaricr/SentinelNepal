from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import AdminUser, Audit, DbSession
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
def list_users(
    _: AdminUser, db: DbSession, paging: Annotated[PageParams, Depends(page_params)]
) -> Page[UserOut]:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    rows = db.scalars(
        select(User).order_by(User.username).offset(paging.offset).limit(paging.page_size)
    ).all()
    return Page(
        items=[UserOut.model_validate(u) for u in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, _: AdminUser, ctx: Audit, db: DbSession) -> UserOut:
    user = users.create_user(db, ctx, body.username, body.password, body.role)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, _: AdminUser, ctx: Audit, db: DbSession) -> UserOut:
    user = users.update_user(
        db, ctx, user_id, role=body.role, is_active=body.is_active, password=body.password
    )
    return UserOut.model_validate(user)
