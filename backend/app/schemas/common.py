from typing import Annotated, Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict

MAX_PAGE_SIZE = 100

# Literal types for API schemas, so clients see the allowed values. They mirror the tuples
# in app/models/enums.py (the database CHECK constraints); a unit test keeps them equal.
AlertSource = Literal["dataset", "live", "replay"]
AlertStatus = Literal["new", "acknowledged", "linked", "dismissed"]
AttackCategory = Literal[
    "Analysis",
    "Backdoor",
    "DoS",
    "Exploits",
    "Fuzzers",
    "Generic",
    "Reconnaissance",
    "Shellcode",
    "Worms",
]
Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["new", "under_investigation", "confirmed", "false_positive", "resolved"]
FirewallStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "executing",
    "active",
    "failed",
    "expired",
    "revoke_requested",
    "revoked",
    "unknown",
]
AuditActorType = Literal["user", "system", "collector", "helper", "anonymous"]
AuditOutcome = Literal["success", "failure", "denied"]


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
