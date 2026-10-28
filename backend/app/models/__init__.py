"""ORM models. Import every model here so Alembic sees the complete metadata."""

from app.models.alert import Alert
from app.models.analysis import DatasetAnalysisRun
from app.models.audit import AuditLog
from app.models.collector import Collector
from app.models.firewall import FirewallActionResult, FirewallRequest
from app.models.incident import Incident, IncidentAlert, InvestigationNote
from app.models.model_version import ModelVersion
from app.models.recommendation import Recommendation
from app.models.session import UserSession
from app.models.user import User

__all__ = [
    "Alert",
    "AuditLog",
    "Collector",
    "DatasetAnalysisRun",
    "FirewallActionResult",
    "FirewallRequest",
    "Incident",
    "IncidentAlert",
    "InvestigationNote",
    "ModelVersion",
    "Recommendation",
    "User",
    "UserSession",
]
