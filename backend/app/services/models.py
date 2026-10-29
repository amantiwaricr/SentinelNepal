"""Model registry: which trained artifacts may be used, with their trusted SHA-256."""

import json
from pathlib import Path
from typing import Any, Literal

from sentinel_ml.artifacts import MODEL_FILE, ArtifactError, load_manifest
from sentinel_ml.features.dataset import sha256_file
from sentinel_ml.live.mapping import check_compatibility
from sentinel_ml.schema import NORMAL
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.models.model_version import ModelVersion
from app.services import audit
from app.services.audit import AuditContext

# Below this per-class precision a predicted category is called unreliable: most records the
# model gives that label belong to another class. Shown in the UI and used by recommendations.
RELIABLE_PRECISION = 0.5


Split = Literal["test", "validation"]
SPLITS: tuple[Split, ...] = ("test", "validation")


def category_precision(metrics: dict[str, Any]) -> tuple[dict[str, float], Split | None]:
    """Per-class precision recorded at registration: the testing file if evaluated, else the
    validation split. Returns the values and which split they come from."""
    for split in SPLITS:
        values = (metrics.get(split) or {}).get("per_class_precision")
        if values:
            return {str(k): float(v) for k, v in values.items()}, split
    return {}, None


def low_precision_categories(metrics: dict[str, Any]) -> list[str]:
    precision, _ = category_precision(metrics)
    return sorted(c for c, p in precision.items() if c != NORMAL and p < RELIABLE_PRECISION)


def artifact_path(settings: Settings, relative: str) -> Path:
    """Resolve an artifact directory, refusing anything outside MODEL_ARTIFACTS_DIR."""
    root = settings.model_artifacts_dir.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise AppError("invalid_artifact_path", "Artifact path is outside the models directory")
    return path


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _summarise(evaluation: dict[str, Any] | None, validation: dict[str, Any]) -> dict[str, Any]:
    def brief(metrics: dict[str, Any]) -> dict[str, Any]:
        binary = metrics["binary"]
        return {
            "macro_f1": metrics["macro_f1"],
            "attack_recall": binary["recall"],
            "false_positive_rate": binary["false_positive_rate"],
            "per_class_precision": {k: v["precision"] for k, v in metrics["per_class"].items()},
        }

    summary: dict[str, Any] = {"validation": brief(validation)}
    if evaluation is not None:
        summary["test"] = brief(evaluation["all"]) | {"records": evaluation["all"]["records"]}
    return summary


def register_model(
    db: Session,
    settings: Settings,
    ctx: AuditContext,
    artifact_dir: Path,
    *,
    reports_dir: Path | None = None,
    activate: bool = False,
    allow_synthetic: bool = False,
) -> ModelVersion:
    root = settings.model_artifacts_dir.resolve()
    directory = artifact_dir.resolve()
    if not directory.is_relative_to(root):
        raise AppError("invalid_artifact_path", f"Artifact must be inside {root}")
    try:
        manifest = load_manifest(directory)
    except ArtifactError as exc:
        raise AppError("invalid_artifact", str(exc)) from exc
    if manifest.data_origin != "unsw-nb15" and not allow_synthetic:
        raise AppError("invalid_artifact", "Refusing to register a model trained on synthetic data")
    actual = sha256_file(directory / MODEL_FILE)
    if actual != manifest.model_sha256:
        raise AppError("invalid_artifact", "Model file does not match its manifest hash")

    report_dir = (reports_dir / directory.name) if reports_dir else None
    evaluation = _read_json(report_dir / "evaluation.json") if report_dir else None
    threshold = _read_json(report_dir / "threshold.json") if report_dir else None
    for name, payload in (("evaluation", evaluation), ("threshold", threshold)):
        if payload is not None and payload["model"]["sha256"] != actual:
            raise AppError("invalid_artifact", f"{name}.json belongs to a different model file")

    selected = next(
        c for c in manifest.selection["candidates"] if c["name"] == manifest.selection["selected"]
    )
    model = ModelVersion(
        name=manifest.name,
        version=manifest.version,
        model_kind=manifest.model_kind,
        feature_profile=manifest.feature_profile,
        artifact_dir=str(directory.relative_to(root)),
        artifact_sha256=actual,
        features=manifest.features,
        class_labels=manifest.class_labels,
        metrics=_summarise(evaluation, selected["validation"]),
        alert_threshold=threshold["threshold"] if threshold else None,
        threshold_details=(
            {k: threshold[k] for k in ("target_fpr", "chosen", "selected_on")}
            if threshold
            else None
        ),
        registered_by=ctx.actor.id if ctx.actor else None,
    )
    db.add(model)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("conflict", "This model version is already registered", 409) from None
    audit.record(
        db,
        ctx,
        "model.registered",
        target_type="model_version",
        target_id=model.id,
        details={"name": model.name, "version": model.version, "sha256": actual},
    )
    if activate:
        activate_model(db, ctx, model.id, commit=False)
    db.commit()
    return model


def activate_model(
    db: Session, ctx: AuditContext, model_id: int, *, commit: bool = True
) -> ModelVersion:
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise AppError("not_found", "Model version not found", 404)
    previous = db.scalar(
        select(ModelVersion.id).where(
            ModelVersion.feature_profile == model.feature_profile,
            ModelVersion.is_active,
            ModelVersion.id != model.id,
        )
    )
    db.execute(
        update(ModelVersion)
        .where(ModelVersion.feature_profile == model.feature_profile, ModelVersion.id != model.id)
        .values(is_active=False)
    )
    db.flush()
    model.is_active = True
    model.activated_at = utcnow()
    audit.record(
        db,
        ctx,
        "model.activated",
        target_type="model_version",
        target_id=model.id,
        details={"feature_profile": model.feature_profile, "previous_active_id": previous},
    )
    if commit:
        db.commit()
    return model


def active_model(db: Session, profile: str) -> ModelVersion | None:
    return db.scalar(
        select(ModelVersion).where(ModelVersion.feature_profile == profile, ModelVersion.is_active)
    )


def set_live_approval(
    db: Session, ctx: AuditContext, model_id: int, approved: bool
) -> ModelVersion:
    """Approve (or withdraw) a model for scoring live TShark flows. Approval is refused when
    the model needs a feature live traffic cannot supply."""
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise AppError("not_found", "Model not found", 404)
    report = check_compatibility(model.features)
    if approved and not report.compatible:
        audit.record(
            db,
            ctx,
            "model.live_approval",
            target_type="model_version",
            target_id=model.id,
            outcome="denied",
            details={"approved": True, "unavailable": report.unavailable},
        )
        db.commit()
        raise AppError("incompatible_model", report.reason, 409)
    model.live_inference_approved = approved
    audit.record(
        db,
        ctx,
        "model.live_approval",
        target_type="model_version",
        target_id=model.id,
        details={"approved": approved, "approximate_features": report.approximate},
    )
    db.commit()
    return model
