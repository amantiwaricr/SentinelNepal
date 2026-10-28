"""Model artifact layout, manifest, and integrity checks.

An artifact is a directory ``<name>-<version>/`` containing:

* ``model.joblib`` — the fitted scikit-learn Pipeline (preprocessing + model);
* ``manifest.json`` — everything needed to reproduce and audit it.

joblib files are pickles: loading one can execute code. Only artifacts produced locally by the
team are loaded, and only after their SHA-256 matches a trusted record (the backend keeps the
hash in its ``model_versions`` table).
"""

from __future__ import annotations

import hmac
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline

from sentinel_ml.features.dataset import sha256_file

MODEL_FILE = "model.joblib"
MANIFEST_FILE = "manifest.json"


class ArtifactError(Exception):
    """The artifact is missing, malformed, incompatible, or failed its integrity check."""


@dataclass
class ModelManifest:
    name: str
    version: str
    model_kind: str
    feature_profile: str
    feature_schema_version: int
    numeric_features: list[str]
    categorical_features: list[str]
    class_labels: list[str]
    data_origin: str
    training_sources: list[dict[str, Any]]
    seed: int
    hyperparameters: dict[str, Any]
    selection: dict[str, Any]
    feature_importance: dict[str, float]
    environment: dict[str, str]
    created_at: str
    git_commit: str | None
    model_sha256: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def features(self) -> list[str]:
        return [*self.numeric_features, *self.categorical_features]


def save_artifact(pipeline: Pipeline, manifest: ModelManifest, artifacts_dir: Path) -> Path:
    target = artifacts_dir / f"{manifest.name}-{manifest.version}"
    if target.exists():
        raise ArtifactError(f"Refusing to overwrite existing artifact {target}")
    target.mkdir(parents=True)
    model_path = target / MODEL_FILE
    joblib.dump(pipeline, model_path)
    manifest.model_sha256 = sha256_file(model_path)
    (target / MANIFEST_FILE).write_text(
        json.dumps(asdict(manifest), indent=2) + "\n", encoding="utf-8"
    )
    return target


def load_manifest(artifact_dir: Path) -> ModelManifest:
    path = artifact_dir / MANIFEST_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ModelManifest(**data)
    except FileNotFoundError:
        raise ArtifactError(f"No {MANIFEST_FILE} in {artifact_dir}") from None
    except (json.JSONDecodeError, TypeError) as exc:
        raise ArtifactError(f"Malformed {MANIFEST_FILE} in {artifact_dir}") from exc


def verify_model_file(artifact_dir: Path, expected_sha256: str) -> Path:
    model_path = artifact_dir / MODEL_FILE
    if not model_path.is_file():
        raise ArtifactError(f"No {MODEL_FILE} in {artifact_dir}")
    actual = sha256_file(model_path)
    if not hmac.compare_digest(actual, expected_sha256.lower()):
        raise ArtifactError(
            f"Integrity check failed for {model_path}: SHA-256 does not match the trusted value"
        )
    return model_path


def load_pipeline(artifact_dir: Path, expected_sha256: str) -> Pipeline:
    """Load the model only after its hash matches ``expected_sha256``."""
    model_path = verify_model_file(artifact_dir, expected_sha256)
    pipeline = joblib.load(model_path)  # safe only because the hash was verified first
    if not isinstance(pipeline, Pipeline):
        raise ArtifactError(f"{model_path} does not contain a scikit-learn Pipeline")
    return pipeline
