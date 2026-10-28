import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import default_sessionmaker
from app.models.audit import AuditLog
from app.models.model_version import ModelVersion
from app.services.audit import AuditContext
from app.services.models import register_model

SYSTEM = AuditContext.system("test")


def test_registration_records_trusted_hash_metrics_and_threshold(
    registered_model: ModelVersion, model_artifacts: dict[str, Path]
) -> None:
    from sentinel_ml.artifacts import load_manifest

    manifest = load_manifest(model_artifacts["artifact_dir"])
    assert registered_model.artifact_sha256 == manifest.model_sha256
    assert registered_model.is_active and registered_model.feature_profile == "full"
    assert registered_model.alert_threshold is not None
    assert registered_model.threshold_details["selected_on"].startswith("validation split")
    assert "validation" in registered_model.metrics


def test_synthetic_models_are_refused_by_default(
    db: Session, app_settings: Settings, model_artifacts: dict[str, Path]
) -> None:
    with pytest.raises(AppError, match="synthetic"):
        register_model(db, app_settings, SYSTEM, model_artifacts["artifact_dir"])


def test_artifacts_outside_the_models_directory_are_refused(
    db: Session, app_settings: Settings, model_artifacts: dict[str, Path], tmp_path: Path
) -> None:
    outside = tmp_path / "elsewhere"
    shutil.copytree(model_artifacts["artifact_dir"], outside)
    with pytest.raises(AppError, match="inside"):
        register_model(db, app_settings, SYSTEM, outside, allow_synthetic=True)


def test_tampered_artifact_is_refused(
    db: Session, model_artifacts: dict[str, Path], tmp_path: Path, database_url: str
) -> None:
    from tests.conftest import make_settings

    root = tmp_path / "artifacts"
    copy = root / model_artifacts["artifact_dir"].name
    shutil.copytree(model_artifacts["artifact_dir"], copy)
    with (copy / "model.joblib").open("ab") as handle:
        handle.write(b"x")
    settings = make_settings(database_url=database_url, model_artifacts_dir=root)
    with pytest.raises(AppError, match="does not match"):
        register_model(db, settings, SYSTEM, copy, allow_synthetic=True)


def test_duplicate_registration_conflicts(
    db: Session,
    app_settings: Settings,
    registered_model: ModelVersion,
    model_artifacts: dict[str, Path],
) -> None:
    with pytest.raises(AppError) as excinfo:
        register_model(
            db, app_settings, SYSTEM, model_artifacts["artifact_dir"], allow_synthetic=True
        )
    assert excinfo.value.status_code == 409


def test_cli_registers_and_activates(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    model_artifacts: dict[str, Path],
    clean_db: object,
    db: Session,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("MODEL_ARTIFACTS_DIR", str(model_artifacts["artifacts"]))
    get_settings.cache_clear()
    default_sessionmaker.cache_clear()
    try:
        code = cli.main(
            [
                "register-model",
                str(model_artifacts["artifact_dir"]),
                "--reports-dir",
                str(model_artifacts["reports"]),
                "--activate",
                "--allow-synthetic",
            ]
        )
    finally:
        get_settings.cache_clear()
        default_sessionmaker.cache_clear()
    assert code == 0
    assert "alert threshold" in capsys.readouterr().out
    model = db.scalars(select(ModelVersion)).one()
    assert model.is_active
    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"model.registered", "model.activated"} <= actions


def test_models_api_and_activation_roles(
    admin: TestClient, analyst: TestClient, registered_model: ModelVersion
) -> None:
    listing = analyst.get("/api/v1/models")
    assert listing.status_code == 200 and listing.json()[0]["id"] == registered_model.id
    assert analyst.get("/api/v1/models/active").json()[0]["is_active"] is True
    assert analyst.post(f"/api/v1/models/{registered_model.id}/activate").status_code == 403
    assert admin.post(f"/api/v1/models/{registered_model.id}/activate").status_code == 200
    assert admin.post("/api/v1/models/9999/activate").status_code == 404
