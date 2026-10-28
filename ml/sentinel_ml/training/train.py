"""Train candidate models and select one using the validation split only.

The official testing file is never read here; it is used once, afterwards, by
``sentinel_ml.evaluation.evaluate``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from sentinel_ml.artifacts import ModelManifest, save_artifact
from sentinel_ml.environment import environment_info, git_commit
from sentinel_ml.evaluation.metrics import classification_metrics
from sentinel_ml.evaluation.report import render_training_markdown
from sentinel_ml.features.dataset import DatasetError, find_file, load_files
from sentinel_ml.preprocessing.pipeline import (
    ModelKind,
    build_pipeline,
    global_feature_importance,
)
from sentinel_ml.schema import CLASS_LABELS, FEATURE_SCHEMA_VERSION, TRAIN_FILE, get_profile

DEFAULT_SEED = 42

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    kind: ModelKind
    class_weight: Literal["balanced"] | None


CANDIDATES = (
    CandidateSpec("logistic_regression", "logistic_regression", None),
    CandidateSpec("logistic_regression_balanced", "logistic_regression", "balanced"),
    CandidateSpec("random_forest", "random_forest", None),
    CandidateSpec("random_forest_balanced", "random_forest", "balanced"),
)


@dataclass
class TrainingResult:
    artifact_dir: Path
    manifest: ModelManifest
    report_dir: Path


def _simple_params(pipeline: Pipeline) -> dict[str, Any]:
    params = pipeline.named_steps["model"].get_params()
    return {k: v for k, v in params.items() if isinstance(v, str | int | float | bool | None)}


def fit_warnings(pipeline: Pipeline) -> list[str]:
    """Problems that qualify a fitted candidate's results, read from the fitted model.

    Checked explicitly rather than by capturing Python warnings: ``warnings.catch_warnings``
    is not thread-safe, and Random Forest fits run on many threads.
    """
    model = pipeline.named_steps["model"]
    if hasattr(model, "n_iter_") and hasattr(model, "max_iter"):
        iterations = int(np.max(model.n_iter_))
        if iterations >= model.max_iter:
            return [
                f"ConvergenceWarning: solver stopped at max_iter={model.max_iter} "
                "before converging; the baseline may be under-fitted"
            ]
    return []


def _selection_key(result: dict[str, Any]) -> tuple[float, float]:
    validation = result["validation"]
    # Highest macro-F1; ties broken by the lower false-positive rate on Normal traffic.
    return (validation["macro_f1"], -validation["binary"]["false_positive_rate"])


def train_model(
    data_dir: Path,
    artifacts_dir: Path,
    reports_dir: Path,
    *,
    profile_name: str = "full",
    seed: int = DEFAULT_SEED,
    validation_fraction: float = 0.2,
    rf_estimators: int = 200,
    n_jobs: int = -1,
    candidates: tuple[CandidateSpec, ...] = CANDIDATES,
    version: str | None = None,
) -> TrainingResult:
    if not candidates:
        raise ValueError("At least one candidate model is required")
    profile = get_profile(profile_name)
    train_path = find_file(data_dir, TRAIN_FILE)
    logger.info("Loading %s (profile %r)", train_path.name, profile.name)
    dataset = load_files([train_path], data_dir=data_dir)
    logger.info("Read %d rows; %d rejected by validation", dataset.rows_read, dataset.rows_rejected)

    features = dataset.features[list(profile.features)]
    labels = dataset.labels
    # Exact duplicates (same features and label) would otherwise appear on both sides of the
    # train/validation split and inflate validation scores.
    duplicated = features.assign(_label=labels).duplicated().to_numpy()
    features, labels = features[~duplicated], labels[~duplicated]

    class_counts = labels.value_counts()
    too_small = class_counts[class_counts < 2]
    if not too_small.empty:
        raise DatasetError(
            f"Classes with fewer than 2 records cannot be split: {too_small.to_dict()}"
        )

    x_train, x_val, y_train, y_val = train_test_split(
        features, labels, test_size=validation_fraction, stratify=labels, random_state=seed
    )

    logger.info(
        "Removed %d duplicate rows; %d train / %d validation rows",
        int(duplicated.sum()),
        len(x_train),
        len(x_val),
    )
    results: list[dict[str, Any]] = []
    best: tuple[dict[str, Any], Pipeline] | None = None
    for number, spec in enumerate(candidates, start=1):
        logger.info("Fitting candidate %d/%d: %s ...", number, len(candidates), spec.name)
        pipeline = build_pipeline(
            profile,
            spec.kind,
            seed=seed,
            class_weight=spec.class_weight,
            rf_estimators=rf_estimators,
            n_jobs=n_jobs,
        )
        started = time.perf_counter()
        pipeline.fit(x_train, y_train)
        fit_seconds = time.perf_counter() - started
        predictions = pipeline.predict(x_val)
        validation = classification_metrics(y_val.tolist(), predictions.tolist(), CLASS_LABELS)
        result: dict[str, Any] = {
            "name": spec.name,
            "kind": spec.kind,
            "class_weight": spec.class_weight,
            "fit_seconds": fit_seconds,
            "warnings": fit_warnings(pipeline),
            "validation": validation,
        }
        results.append(result)
        logger.info(
            "  %s done in %.1f s; validation macro-F1 %.4f",
            spec.name,
            fit_seconds,
            validation["macro_f1"],
        )
        # Keep only the best fitted pipeline in memory; forests can be large.
        if best is None or _selection_key(result) > _selection_key(best[0]):
            best = (result, pipeline)

    if best is None:  # unreachable: candidates is non-empty
        raise RuntimeError("No candidate was trained")
    selected, pipeline = best
    version = version or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    manifest = ModelManifest(
        name=f"{selected['kind']}-{profile.name}",
        version=version,
        model_kind=selected["kind"],
        feature_profile=profile.name,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        numeric_features=list(profile.numeric),
        categorical_features=list(profile.categorical),
        class_labels=[str(c) for c in pipeline.classes_],
        data_origin=dataset.origin,
        training_sources=[vars(source) for source in dataset.sources],
        seed=seed,
        hyperparameters={"candidate": selected["name"], **_simple_params(pipeline)},
        selection={
            "criterion": "validation macro-F1, ties broken by lower false-positive rate",
            "validation_fraction": validation_fraction,
            "rows_read": dataset.rows_read,
            "rows_rejected": dataset.rows_rejected,
            "rejection_counts": dict(dataset.rejection_counts),
            "duplicates_removed": int(duplicated.sum()),
            "train_rows": len(x_train),
            "validation_rows": len(x_val),
            "train_class_counts": {str(k): int(v) for k, v in y_train.value_counts().items()},
            "selected": selected["name"],
            "candidates": results,
        },
        feature_importance=global_feature_importance(pipeline, profile),
        environment=environment_info(),
        created_at=datetime.now(UTC).isoformat(),
        git_commit=git_commit(),
        notes=[
            "Model scores are uncalibrated and must not be read as probabilities.",
            "The official testing file was not used for training or model selection.",
        ],
    )
    logger.info("Selected %s; saving artifact", selected["name"])
    artifact_dir = save_artifact(pipeline, manifest, artifacts_dir)

    report_dir = reports_dir / artifact_dir.name
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = _training_payload(manifest)
    (report_dir / "training.json").write_text(json.dumps(payload, indent=2) + "\n")
    (report_dir / "training.md").write_text(render_training_markdown(payload))
    return TrainingResult(artifact_dir=artifact_dir, manifest=manifest, report_dir=report_dir)


def _training_payload(manifest: ModelManifest) -> dict[str, Any]:
    return {
        "model": {
            "name": manifest.name,
            "version": manifest.version,
            "sha256": manifest.model_sha256,
        },
        "data_origin": manifest.data_origin,
        "feature_profile": manifest.feature_profile,
        "features": manifest.features,
        "training_sources": manifest.training_sources,
        "seed": manifest.seed,
        "selection": manifest.selection,
        "feature_importance": manifest.feature_importance,
        "environment": manifest.environment,
        "git_commit": manifest.git_commit,
        "created_at": manifest.created_at,
    }
