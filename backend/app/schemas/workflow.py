"""Schemas for incidents, notes, firewall requests, and audit logs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, IPvAnyAddress, IPvAnyNetwork

from app.models.incident import MAX_NOTE_LENGTH
from app.schemas.common import (
    AuditActorType,
    AuditOutcome,
    FirewallStatus,
    IncidentStatus,
    OrmModel,
    Severity,
    StrictModel,
)
from app.schemas.ops import AlertOut


class IncidentCreate(StrictModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=MAX_NOTE_LENGTH)
    severity: Severity = "medium"
    alert_ids: list[int] = Field(default_factory=list, max_length=500)
    assigned_to: int | None = None
    # No "status" field: every incident starts as "new".


class IncidentUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    severity: Severity | None = None
    status: IncidentStatus | None = None
    assigned_to: int | None = None  # send null explicitly to unassign


class LinkAlerts(StrictModel):
    alert_ids: list[int] = Field(min_length=1, max_length=500)


class IncidentOut(OrmModel):
    id: int
    title: str
    description: str
    status: IncidentStatus
    severity: Severity
    created_by: int
    assigned_to: int | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    alert_count: int = 0


class IncidentDetail(IncidentOut):
    alerts: list[AlertOut]
    allowed_transitions: list[IncidentStatus]


class NoteCreate(StrictModel):
    body: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)


class NoteOut(OrmModel):
    id: int
    incident_id: int
    author_id: int
    author_username: str
    body: str
    created_at: datetime


class FirewallRequestCreate(StrictModel):
    target: str = Field(min_length=2, max_length=64, description="IP address or CIDR")
    duration_seconds: int = Field(ge=60, le=86_400)
    reason: str = Field(min_length=10, max_length=1000)
    alert_id: int | None = None
    incident_id: int | None = None
    dry_run: bool = False


class FirewallApprove(StrictModel):
    confirm_target: str = Field(min_length=2, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class FirewallReject(StrictModel):
    note: str = Field(min_length=3, max_length=1000)


class FirewallRevoke(StrictModel):
    note: str | None = Field(default=None, max_length=1000)


class FirewallActionResultOut(OrmModel):
    id: int
    operation: str
    success: bool
    error_code: str | None
    error_message: str | None
    executed_at: datetime


class FirewallRequestOut(OrmModel):
    id: int
    target: IPvAnyNetwork
    ip_version: int
    reason: str
    alert_id: int | None
    incident_id: int | None
    requested_by: int
    status: FirewallStatus
    duration_seconds: int
    dry_run: bool
    approved_by: int | None
    approved_at: datetime | None
    decision_note: str | None
    applied_at: datetime | None
    expires_at: datetime | None
    revoked_by: int | None
    revoked_at: datetime | None
    created_at: datetime
    results: list[FirewallActionResultOut] = Field(default_factory=list)
    # True only once the helper has confirmed the rule (Phase 7). Never inferred from status.
    applied: bool = False


class FirewallStatusOut(StrictModel):
    helper: Literal["not_configured"]
    detail: str
    protected_networks: list[str]
    max_duration_seconds: int
    self_approval_allowed: bool


class AuditLogOut(OrmModel):
    id: int
    occurred_at: datetime
    actor_type: AuditActorType
    actor_user_id: int | None
    actor_label: str | None
    action: str
    target_type: str | None
    target_id: str | None
    outcome: AuditOutcome
    ip_address: IPvAnyAddress | None
    request_id: str | None
    details: dict[str, Any]
