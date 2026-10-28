"""Allowed values shared by database CHECK constraints and API schemas."""

from sentinel_ml.schema import ATTACK_CATEGORIES

USER_ROLES = ("admin", "analyst")

ANALYSIS_STATUSES = ("queued", "running", "completed", "failed")

ALERT_SOURCES = ("dataset", "live", "replay")
ALERT_STATUSES = ("new", "acknowledged", "linked", "dismissed")
SEVERITIES = ("low", "medium", "high", "critical")
PREDICTED_CATEGORIES = ATTACK_CATEGORIES  # alerts are only raised for attack classes

INCIDENT_STATUSES = ("new", "under_investigation", "confirmed", "false_positive", "resolved")

FIREWALL_STATUSES = (
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
)
# A target may have at most one request in one of these states at a time.
FIREWALL_OPEN_STATUSES = (
    "pending",
    "approved",
    "executing",
    "active",
    "revoke_requested",
    "unknown",
)
FIREWALL_OPERATIONS = ("apply", "revoke", "verify", "expire_check")

COLLECTOR_MODES = ("observation", "inference")

AUDIT_ACTOR_TYPES = ("user", "system", "collector", "helper", "anonymous")
AUDIT_OUTCOMES = ("success", "failure", "denied")


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """CHECK constraint text: ``column IN ('a', 'b')``. Values are fixed constants above."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
