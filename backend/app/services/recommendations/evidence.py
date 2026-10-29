"""Facts about one alert, and the named evidence checks rules can require.

Every check looks only at data SentinelNepal stored: the alert's own fields, the model's
recorded per-class precision, and counts of other stored alerts. Nothing is looked up
externally, and nothing is assumed when a value is missing: a missing value fails the check.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.services.alerts import STRONG_SCORE
from app.services.models import RELIABLE_PRECISION

REPEATED_ALERTS = 5  # alerts from one source before "repeated activity" counts as evidence
MANY_PORTS = 5  # distinct destination ports from one source before it looks like a scan

# Services and ports where repeated connections can indicate password guessing.
AUTH_SERVICES = frozenset({"ssh", "ftp", "telnet", "pop3", "imap", "smtp", "rdp"})
AUTH_PORTS = frozenset({21, 22, 23, 25, 110, 143, 465, 587, 993, 995, 3389})


@dataclass(frozen=True)
class AlertFacts:
    category: str
    attack_score: float
    default_decision: str | None
    src_ip: str | None
    dst_ip: str | None
    dst_port: int | None
    service: str | None
    # Model precision for this category, and which split it was measured on.
    category_precision: float | None
    precision_source: str | None
    # Counts over stored alerts in the same scope (same analysis run, or same live source
    # within a day). None when the source address is unknown.
    alerts_from_source: int | None
    distinct_ports_from_source: int | None
    alerts_to_same_target: int | None

    @property
    def known_service(self) -> str | None:
        return self.service if self.service and self.service != "-" else None

    @property
    def targets_auth_service(self) -> bool:
        return (self.known_service or "") in AUTH_SERVICES or (self.dst_port or -1) in AUTH_PORTS


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    description: str
    check: Callable[[AlertFacts], bool]
    observed: Callable[[AlertFacts], str]


def _value(value: object) -> str:
    return "not recorded" if value is None else str(value)


def _count(value: int | None, noun: str) -> str:
    if value is None:
        return "not recorded"
    return f"{value} {noun}" if value == 1 else f"{value} {noun}s"


CHECKS: dict[str, EvidenceCheck] = {
    c.name: c
    for c in (
        EvidenceCheck(
            "source_address",
            "The source IP address is recorded",
            lambda f: f.src_ip is not None,
            lambda f: _value(f.src_ip),
        ),
        EvidenceCheck(
            "destination_address",
            "The destination IP address is recorded",
            lambda f: f.dst_ip is not None,
            lambda f: _value(f.dst_ip),
        ),
        EvidenceCheck(
            "destination_service",
            "The destination port or service is recorded",
            lambda f: f.dst_port is not None or f.known_service is not None,
            lambda f: f"port {_value(f.dst_port)}, service {_value(f.known_service)}",
        ),
        EvidenceCheck(
            "strong_score",
            f"The attack score is at least {STRONG_SCORE} (uncalibrated)",
            lambda f: f.attack_score >= STRONG_SCORE,
            lambda f: f"{f.attack_score:.3f}",
        ),
        EvidenceCheck(
            "model_agrees",
            "The model's highest-scoring class is this attack category, not just above threshold",
            lambda f: f.default_decision == f.category,
            lambda f: f"highest class {_value(f.default_decision)}",
        ),
        EvidenceCheck(
            "reliable_category",
            f"The model's recorded precision for this category is at least "
            f"{RELIABLE_PRECISION:.0%}",
            lambda f: (
                f.category_precision is not None and f.category_precision >= RELIABLE_PRECISION
            ),
            lambda f: (
                "not recorded"
                if f.category_precision is None
                else f"{f.category_precision:.1%} on the {f.precision_source} data"
            ),
        ),
        EvidenceCheck(
            "repeated_from_source",
            f"At least {REPEATED_ALERTS} stored alerts from the same source",
            lambda f: (f.alerts_from_source or 0) >= REPEATED_ALERTS,
            lambda f: _count(f.alerts_from_source, "alert"),
        ),
        EvidenceCheck(
            "many_ports_from_source",
            f"Alerts from the same source to at least {MANY_PORTS} different destination ports",
            lambda f: (f.distinct_ports_from_source or 0) >= MANY_PORTS,
            lambda f: _count(f.distinct_ports_from_source, "port"),
        ),
        EvidenceCheck(
            "repeated_to_auth_service",
            f"At least {REPEATED_ALERTS} alerts from the same source to this authentication "
            "service",
            lambda f: f.targets_auth_service and (f.alerts_to_same_target or 0) >= REPEATED_ALERTS,
            lambda f: (
                f"{_value(f.alerts_to_same_target)} alerts to "
                f"{_value(f.known_service or f.dst_port)}"
            ),
        ),
    )
}


def evaluate(names: tuple[str, ...], facts: AlertFacts) -> dict[str, dict[str, object]]:
    """Each required check with whether it was met and what was observed."""
    return {
        name: {
            "met": CHECKS[name].check(facts),
            "description": CHECKS[name].description,
            "observed": CHECKS[name].observed(facts),
        }
        for name in names
    }
