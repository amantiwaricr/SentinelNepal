from typing import Literal

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    status: Literal["ok", "pending", "unavailable", "unknown"]
    detail: str | None = None


class LivenessOut(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadinessOut(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    version: str
    environment: str
    components: dict[str, ComponentStatus]
