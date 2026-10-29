"""API Literal types must allow exactly the values the database CHECK constraints allow."""

from typing import get_args

import pytest

from app.models import enums
from app.schemas import common


@pytest.mark.parametrize(
    ("literal", "values"),
    [
        (common.AlertSource, enums.ALERT_SOURCES),
        (common.AlertStatus, enums.ALERT_STATUSES),
        (common.AttackCategory, enums.PREDICTED_CATEGORIES),
        (common.Severity, enums.SEVERITIES),
        (common.IncidentStatus, enums.INCIDENT_STATUSES),
        (common.FirewallStatus, enums.FIREWALL_STATUSES),
        (common.AuditActorType, enums.AUDIT_ACTOR_TYPES),
        (common.AuditOutcome, enums.AUDIT_OUTCOMES),
    ],
)
def test_literal_matches_database_values(literal: object, values: tuple[str, ...]) -> None:
    assert get_args(literal) == tuple(values)
