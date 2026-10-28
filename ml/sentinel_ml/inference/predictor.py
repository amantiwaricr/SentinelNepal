"""Prediction service used by the backend (dataset analysis) and, later, live inference.

Outputs are *predictions*: a suspected category and an uncalibrated model score. They are
evidence for an analyst to review, never proof that an attack happened.
"""

from __future__ import annotations

import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from sentinel_ml.artifacts import ArtifactError, ModelManifest, load_manifest, load_pipeline
from sentinel_ml.environment import library_versions
from sentinel_ml.features.cleaning import clean_frame
from sentinel_ml.schema import (
    CATEGORICAL_FEATURES,
    CLASS_LABELS,
    FEATURE_SCHEMA_VERSION,
    NORMAL,
    NULLABLE_FEATURES,
)

MAX_BATCH_RECORDS = 10_000


@dataclass(frozen=True)
class Prediction:
    index: int  # position of the record in the input
    predicted_category: str
    is_suspicious: bool  # predicted category is not Normal
    model_score: float  # uncalibrated score of the predicted category, not a probability
    class_scores: dict[str, float]
    imputed_features: list[str]  # nullable features that were blank and filled by the model
    unknown_categories: dict[str, str]  # categorical values never seen in training


@dataclass(frozen=True)
class RejectedRecord:
    index: int
    reasons: list[str]


@dataclass
class PredictionBatch:
    model_name: str
    model_version: str
    feature_profile: str
    predictions: list[Prediction] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)


class Predictor:
    def __init__(self, pipeline: Pipeline, manifest: ModelManifest) -> None:
        self._pipeline = pipeline
        self._manifest = manifest
        self._classes = [str(c) for c in pipeline.classes_]
        unexpected = set(self._classes) - set(CLASS_LABELS)
        if unexpected:
            raise ArtifactError(f"Model predicts unsupported classes: {sorted(unexpected)}")
        fitted_columns = [str(c) for c in pipeline.named_steps["preprocess"].feature_names_in_]
        if fitted_columns != manifest.features:
            raise ArtifactError("Model input columns do not match the manifest feature list")
        self._known_categories = self._categories_seen_in_training()

    @classmethod
    def load(cls, artifact_dir: Path, expected_sha256: str) -> Predictor:
        """Load an artifact whose model file must hash to ``expected_sha256``."""
        manifest = load_manifest(artifact_dir)
        if not hmac.compare_digest(manifest.model_sha256, expected_sha256.lower()):
            raise ArtifactError("Manifest hash does not match the trusted value")
        trained_with = manifest.environment.get("scikit-learn")
        installed = library_versions()["scikit-learn"]
        if trained_with != installed:
            # Pickled scikit-learn models are only reliable with the version that saved them.
            raise ArtifactError(
                f"Artifact was trained with scikit-learn {trained_with}; installed version is "
                f"{installed}. Retrain the model with the installed version."
            )
        if manifest.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ArtifactError(
                f"Artifact uses feature schema v{manifest.feature_schema_version}; this code "
                f"expects v{FEATURE_SCHEMA_VERSION}. Retrain the model."
            )
        return cls(load_pipeline(artifact_dir, expected_sha256), manifest)

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    @property
    def features(self) -> list[str]:
        return self._manifest.features

    @property
    def class_labels(self) -> list[str]:
        return list(self._classes)

    def global_feature_importance(self, top: int | None = None) -> dict[str, float]:
        """Overall importance per feature. Not an explanation of a single prediction."""
        items = list(self._manifest.feature_importance.items())
        return dict(items[:top] if top else items)

    def _categories_seen_in_training(self) -> dict[str, set[str]]:
        preprocess = self._pipeline.named_steps["preprocess"]
        categorical = [f for f in self.features if f in CATEGORICAL_FEATURES]
        if not categorical:
            return {}
        encoder = preprocess.named_transformers_["categorical"].named_steps["encode"]
        return {
            name: {str(v) for v in values}
            for name, values in zip(categorical, encoder.categories_, strict=True)
        }

    def _empty_batch(self) -> PredictionBatch:
        return PredictionBatch(
            model_name=self._manifest.name,
            model_version=self._manifest.version,
            feature_profile=self._manifest.feature_profile,
        )

    def predict_records(self, records: Sequence[Mapping[str, object]]) -> PredictionBatch:
        """Predict for JSON-like records with canonical (or aliased) feature names."""
        if len(records) > MAX_BATCH_RECORDS:
            raise ValueError(f"At most {MAX_BATCH_RECORDS} records per call")
        batch = self._empty_batch()
        accepted: list[Mapping[str, object]] = []
        positions: list[int] = []
        for position, record in enumerate(records):
            reasons = self._type_errors(record)
            if reasons:
                batch.rejected.append(RejectedRecord(position, reasons))
            else:
                accepted.append(record)
                positions.append(position)
        if accepted:
            frame = pd.DataFrame([{f: r.get(f) for f in self.features} for r in accepted])
            self._predict_into(batch, frame.astype(object), positions)
        batch.rejected.sort(key=lambda r: r.index)
        return batch

    def predict_frame(self, frame: pd.DataFrame) -> PredictionBatch:
        """Predict for a DataFrame (e.g. an uploaded CSV). Values are validated per row."""
        if len(frame) > MAX_BATCH_RECORDS:
            raise ValueError(f"At most {MAX_BATCH_RECORDS} records per call")
        batch = self._empty_batch()
        if not frame.empty:
            self._predict_into(batch, frame, list(range(len(frame))))
        return batch

    def _type_errors(self, record: Mapping[str, object]) -> list[str]:
        reasons = []
        for name in self.features:
            if name not in record:
                reasons.append(f"missing_field:{name}")
                continue
            value = record[name]
            if value is None:
                continue  # judged by clean_frame (allowed only for nullable features)
            if name in CATEGORICAL_FEATURES:
                ok = isinstance(value, str)
            else:
                ok = isinstance(value, int | float) and not isinstance(value, bool)
            if not ok:
                reasons.append(f"invalid_type:{name}")
        return reasons

    def _predict_into(
        self, batch: PredictionBatch, frame: pd.DataFrame, positions: list[int]
    ) -> None:
        cleaned = clean_frame(frame, self.features, require_labels=False)
        for local, reasons in cleaned.rejected.items():
            batch.rejected.append(RejectedRecord(positions[local], reasons))
        valid_positions = [p for i, p in enumerate(positions) if i not in cleaned.rejected]
        if not valid_positions:
            return

        features = cleaned.features[self.features]
        probabilities = self._pipeline.predict_proba(features)
        nullable = [f for f in self.features if f in NULLABLE_FEATURES]
        for row, position in enumerate(valid_positions):
            scores = probabilities[row]
            best = int(np.argmax(scores))
            category = self._classes[best]
            values = features.iloc[row]
            batch.predictions.append(
                Prediction(
                    index=position,
                    predicted_category=category,
                    is_suspicious=category != NORMAL,
                    model_score=float(scores[best]),
                    class_scores={c: float(s) for c, s in zip(self._classes, scores, strict=True)},
                    imputed_features=[f for f in nullable if pd.isna(values[f])],
                    unknown_categories={
                        name: str(values[name])
                        for name, known in self._known_categories.items()
                        if str(values[name]) not in known
                    },
                )
            )
