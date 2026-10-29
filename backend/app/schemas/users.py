from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import OrmModel, StrictModel

Role = Literal["admin", "analyst"]
USERNAME_PATTERN = r"^[A-Za-z0-9._-]{3,64}$"


class LoginIn(StrictModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(OrmModel):
    id: int
    username: str
    role: Role
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UserDirectoryEntry(OrmModel):
    """What any signed-in user may see about colleagues: enough to assign work and show names."""

    id: int
    username: str
    role: Role
    is_active: bool


class UserCreate(StrictModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=1, max_length=256)
    role: Role


class UserUpdate(StrictModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=256)
