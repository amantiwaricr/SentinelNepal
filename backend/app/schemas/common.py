from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict

MAX_PAGE_SIZE = 100


class StrictModel(BaseModel):
    """Base for request bodies: unknown fields are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class PageParams(BaseModel):
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)
