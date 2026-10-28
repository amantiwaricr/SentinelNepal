"""Response and request schemas for models, analyses, alerts, investigation, dashboard."""

from datetime import datetime
from typing import Any, Literal

from pydantic import IPvAnyAddress

from app.schemas.common import OrmModel, StrictModel


class ModelVersionOut(OrmModel):
    id: int
    name: str
    version: str
    model_kind: str
    feature_profile: str
    artifact_sha256: str
    features: list[str]
    class_labels: list[str]
    metrics: dict[str, Any]
    alert_threshold: float | None
    threshold_details: dict[str, Any] | None
    is_active: bool
    live_inference_approved: bool
    activated_at: datetime | None
    created_at: datetime


class ModelBrief(OrmModel):
    id: int
    name: str
    version: str
    feature_profile: str


class AnalysisRunOut(OrmModel):
    id: int
    uploaded_by: int
    original_filename: str
    file_sha256: str
    size_bytes: int
    status: Literal["queued", "running", "completed", "failed"]
    detected_schema: str | None
    model_version_id: int | None
    rows_total: int
    rows_valid: int
    rows_rejected: int
    alerts_created: int
    summary: dict[str, Any]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AlertOut(OrmModel):
    id: int
    source: str
    analysis_run_id: int | None
    model_version_id: int
    observed_at: datetime | None
    src_ip: IPvAnyAddress | None
    dst_ip: IPvAnyAddress | None
    src_port: int | None
    dst_port: int | None
    protocol: str | None
    service: str | None
    predicted_category: str
    attack_score: float  # 1 - score(Normal); uncalibrated, not a probability
    severity: str
    status: str
    created_at: datetime


class RecommendationOut(OrmModel):
    id: int
    alert_id: int
    rule_id: str
    rule_version: str
    category: str
    action: str
    reason: str
    required_evidence: list[str]
    evidence_present: dict[str, Any]
    priority: str
    limitations: str
    requires_human_approval: bool
    created_at: datetime


class IncidentBrief(OrmModel):
    id: int
    title: str
    status: str


class AlertDetail(AlertOut):
    evidence: dict[str, Any]
    model: ModelBrief
    recommendations: list[RecommendationOut]
    incidents: list[IncidentBrief]


class AlertStatusUpdate(StrictModel):
    status: Literal["new", "acknowledged", "dismissed"]


class IpSummaryOut(StrictModel):
    ip: str
    version: int
    alerts_total: int
    alerts_as_source: int
    alerts_as_destination: int
    first_seen: datetime | None
    last_seen: datetime | None
    by_category: dict[str, int]
    by_severity: dict[str, int]
    destination_ports: dict[str, int]
    protocols: dict[str, int]
    containing_subnet: str
    alerts_in_subnet: int
    recent_alerts: list[AlertOut]
    note: str


class SubnetSummaryOut(StrictModel):
    cidr: str
    alerts_total: int
    first_seen: datetime | None
    last_seen: datetime | None
    by_category: dict[str, int]
    top_source_ips: dict[str, int]
    top_destination_ips: dict[str, int]


class ActivityPoint(StrictModel):
    day: datetime
    count: int


class ActiveModel(StrictModel):
    id: int
    feature_profile: str
    name: str
    version: str
    alert_threshold: float | None


class DashboardOut(StrictModel):
    source: Literal["all", "dataset", "live"]
    generated_at: datetime
    alerts_total: int
    alerts_new: int
    alerts_by_severity: dict[str, int]
    alerts_by_category: dict[str, int]
    alerts_by_status: dict[str, int]
    alerts_by_source: dict[str, int]
    alert_activity_by_day: list[ActivityPoint]
    top_source_ips: dict[str, int]
    incidents_by_status: dict[str, int]
    analysis_runs_by_status: dict[str, int]
    active_models: list[ActiveModel]
