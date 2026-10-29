"""The live compatibility gate: may TShark-built flows be scored, and if not, why not.

Live flows are scored only when all of these hold:

1. a model is active for the live profile (``LIVE_MODEL_PROFILE``);
2. every feature that model needs can be computed from TShark output (no unavailable
   feature; approximations are listed);
3. an admin approved that model for live use (audited);
4. the collector itself is in ``inference`` mode (checked per collector).

Replayed records carry dataset feature values, so they need only an active model.
"""

from dataclasses import dataclass, field

from sentinel_ml.live.mapping import CompatibilityReport, check_compatibility
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.model_version import ModelVersion
from app.services.models import active_model


@dataclass(frozen=True)
class GateStatus:
    model: ModelVersion | None
    compatibility: CompatibilityReport | None
    approved: bool
    reason: str
    approximate: list[str] = field(default_factory=list)

    @property
    def model_ready(self) -> bool:
        """Conditions 1-3: the model side of the gate is open."""
        return (
            self.model is not None
            and self.compatibility is not None
            and self.compatibility.compatible
            and self.approved
        )


def live_gate(db: Session, settings: Settings) -> GateStatus:
    model = active_model(db, settings.live_model_profile)
    if model is None:
        return GateStatus(
            None,
            None,
            False,
            f"No active model for the live profile '{settings.live_model_profile}'. Register "
            "one with python -m app.cli register-model --activate.",
        )
    report = check_compatibility(model.features)
    if not report.compatible:
        return GateStatus(model, report, model.live_inference_approved, report.reason)
    if not model.live_inference_approved:
        return GateStatus(
            model,
            report,
            False,
            f"An admin has not approved {model.name} {model.version} for live use. "
            f"{report.reason}.",
            report.approximate,
        )
    return GateStatus(
        model,
        report,
        True,
        f"{model.name} {model.version} approved for live use. {report.reason}.",
        report.approximate,
    )


def approve_check(model: ModelVersion) -> CompatibilityReport:
    return check_compatibility(model.features)
