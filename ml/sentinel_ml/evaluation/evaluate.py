"""One-off evaluation of a trained artifact on the official UNSW-NB15 testing file."""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sentinel_ml.artifacts import ArtifactError, load_manifest, load_pipeline
from sentinel_ml.environment import environment_info, git_commit
from sentinel_ml.evaluation.metrics import (
    classification_metrics,
    measure_latency,
    ranking_metrics,
)
from sentinel_ml.evaluation.report import render_evaluation_markdown
from sentinel_ml.features.dataset import LoadedDataset, find_file, load_files
from sentinel_ml.preprocessing.pipeline import configure_for_inference
from sentinel_ml.schema import CLASS_LABELS, NORMAL, TEST_FILE, TRAIN_FILE

logger = logging.getLogger(__name__)


def _row_keys(dataset: LoadedDataset, features: list[str]) -> pd.Series:
    frame = dataset.features[features].assign(_label=dataset.labels.to_numpy())
    return pd.util.hash_pandas_object(frame, index=False)


def evaluate_model(
    artifact_dir: Path,
    data_dir: Path,
    reports_dir: Path,
    *,
    latency_calls: int = 200,
) -> Path:
    logger.info("Loading model %s", artifact_dir.name)
    manifest = load_manifest(artifact_dir)
    # Locally, the hash written by training is the trusted reference; the backend instead uses
    # the hash stored in its database.
    # Same single-threaded configuration as the Predictor, so latency reflects deployment.
    pipeline = configure_for_inference(load_pipeline(artifact_dir, manifest.model_sha256))

    logger.info("Loading training file (to verify it and measure train/test overlap)")
    train = load_files([find_file(data_dir, TRAIN_FILE)], data_dir=data_dir)
    trained_on = {s["name"]: s["sha256"] for s in manifest.training_sources}
    for source in train.sources:
        if trained_on.get(source.name) != source.sha256:
            raise ArtifactError(
                f"{source.name} in {data_dir} differs from the file this model was trained on"
            )

    logger.info("Loading testing file")
    test = load_files([find_file(data_dir, TEST_FILE)], data_dir=data_dir)
    if test.origin != manifest.data_origin:
        raise ArtifactError(
            f"Model trained on {manifest.data_origin} data cannot be evaluated on "
            f"{test.origin} data"
        )

    features = manifest.features
    x_test = test.features[features]
    y_test = test.labels.tolist()
    logger.info("Predicting %d test rows", len(x_test))
    predictions = pipeline.predict(x_test).tolist()
    classes = [str(c) for c in pipeline.classes_]
    probabilities = pipeline.predict_proba(x_test)

    overlap = _row_keys(test, features).isin(set(_row_keys(train, features))).to_numpy()
    unique_true = [y for y, dup in zip(y_test, overlap, strict=True) if not dup]
    unique_pred = [p for p, dup in zip(predictions, overlap, strict=True) if not dup]

    logger.info("Measuring latency and computing metrics")
    payload: dict[str, Any] = {
        "model": {
            "name": manifest.name,
            "version": manifest.version,
            "sha256": manifest.model_sha256,
        },
        "data_origin": test.origin,
        "feature_profile": manifest.feature_profile,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "test_sources": [vars(s) for s in test.sources],
        "rows_read": test.rows_read,
        "rows_rejected": test.rows_rejected,
        "rejection_counts": dict(test.rejection_counts),
        "overlap_with_training": int(overlap.sum()),
        "all": classification_metrics(y_test, predictions, CLASS_LABELS),
        "ranking": (
            ranking_metrics(y_test, probabilities, classes)
            if NORMAL in classes
            else {"roc_auc": None, "average_precision": None}
        ),
        "deduplicated": classification_metrics(unique_true, unique_pred, CLASS_LABELS),
        "latency": measure_latency(pipeline, x_test, single_calls=latency_calls),
        "environment": environment_info(),
        "git_commit": git_commit(),
    }

    logger.info("Writing reports")
    report_dir = reports_dir / artifact_dir.name
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "evaluation.json").write_text(json.dumps(payload, indent=2) + "\n")
    (report_dir / "evaluation.md").write_text(render_evaluation_markdown(payload))
    confusion = payload["all"]["confusion_matrix"]
    with (report_dir / "confusion_matrix.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\predicted", *confusion["labels"]])
        for label, row in zip(confusion["labels"], confusion["matrix"], strict=True):
            writer.writerow([label, *row])
    return report_dir
