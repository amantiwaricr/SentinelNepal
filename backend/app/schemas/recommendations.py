"""The recommendation rule catalogue as published by the API (for transparency)."""

from typing import Literal

from app.schemas.common import StrictModel
from app.schemas.ops import Priority


class EvidenceRequirement(StrictModel):
    name: str
    description: str


class RuleOut(StrictModel):
    rule_id: str
    version: str
    group: str
    categories: list[str]
    kind: Literal["investigate", "harden", "contain"]
    heuristic: bool
    action: str
    reason: str
    required_evidence: list[EvidenceRequirement]
    priority: Priority
    limitations: str
    requires_human_approval: bool
