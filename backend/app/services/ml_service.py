"""Bridge to the sentinel_ml Predictor. Feature handling stays in sentinel_ml; this module
only decides which registered model to load and verifies it against the database record."""

import logging
import threading

from sentinel_ml.artifacts import ArtifactError
from sentinel_ml.inference import Predictor

from app.core.config import Settings
from app.core.errors import AppError
from app.models.model_version import ModelVersion
from app.services.models import artifact_path

logger = logging.getLogger(__name__)


class ModelUnavailableError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("model_unavailable", message, 503)


class PredictorCache:
    """Loaded predictors keyed by model version id. Loading verifies the SHA-256 recorded in
    the database, so a modified file on disk is never used."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._loaded: dict[int, Predictor] = {}

    def get(self, model: ModelVersion) -> Predictor:
        with self._lock:
            predictor = self._loaded.get(model.id)
            if predictor is None:
                path = artifact_path(self._settings, model.artifact_dir)
                try:
                    predictor = Predictor.load(path, expected_sha256=model.artifact_sha256)
                except ArtifactError as exc:
                    logger.error("Model %s could not be loaded: %s", model.id, exc)
                    raise ModelUnavailableError(
                        f"Model {model.name} {model.version} failed its integrity or "
                        "compatibility check"
                    ) from exc
                self._loaded[model.id] = predictor
            return predictor

    def forget(self, model_id: int) -> None:
        with self._lock:
            self._loaded.pop(model_id, None)
