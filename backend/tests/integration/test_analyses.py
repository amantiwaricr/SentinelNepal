from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentinel_ml.inference import Predictor
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.alert import Alert
from app.models.analysis import DatasetAnalysisRun
from app.models.audit import AuditLog
from app.models.model_version import ModelVersion
from app.services.alerts import should_alert
from app.services.analyses import recover_interrupted
from tests.integration.conftest import run_queued_analyses
from tests.integration.helpers import synthetic_csv, synthetic_frame


def _upload(client: TestClient, content: bytes, name: str = "flows.csv"):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/datasets/analyses", files={"file": (name, content, "text/csv")})


def test_upload_is_analysed_and_alerts_match_independent_scoring(
    app: FastAPI,
    analyst: TestClient,
    registered_model: ModelVersion,
    model_artifacts: dict[str, Path],
    db: Session,
) -> None:
    content = synthetic_csv(rows=300, bad_rows=4)
    response = _upload(analyst, content)
    assert response.status_code == 202
    run_id = response.json()["id"]
    assert response.json()["status"] == "queued"

    run_queued_analyses(app)
    run = analyst.get(f"/api/v1/datasets/analyses/{run_id}").json()
    assert run["status"] == "completed", run
    assert (run["rows_total"], run["rows_valid"], run["rows_rejected"]) == (300, 296, 4)
    assert run["summary"]["rejection_reasons"] == {"invalid_value:sbytes": 4}

    # Score the same file independently and apply the same alert rule.
    predictor = Predictor.load(model_artifacts["artifact_dir"], registered_model.artifact_sha256)
    batch = predictor.predict_frame(synthetic_frame(content))
    expected = sum(should_alert(p, registered_model.alert_threshold) for p in batch.predictions)
    stored = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.analysis_run_id == run_id)
    )
    assert run["alerts_created"] == stored == expected
    categories = set(db.scalars(select(Alert.predicted_category)).all())
    assert "Normal" not in categories

    actions = [a.action for a in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert "dataset.uploaded" in actions and "dataset.analysis.completed" in actions


def test_upload_requires_an_active_model(analyst: TestClient) -> None:
    response = _upload(analyst, synthetic_csv(50))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_upload_validation(
    app: FastAPI, analyst: TestClient, registered_model: ModelVersion, app_settings: object
) -> None:
    assert _upload(analyst, b"x,y\n1,2\n", "data.txt").status_code == 415
    assert _upload(analyst, b"\x00\x01binary" * 100).status_code == 422
    assert _upload(analyst, b"").status_code == 422
    app.state.settings.max_upload_mb = 1
    too_big = _upload(analyst, b"a,b,c,d,e,f\n" + b"1,2,3,4,5,6\n" * 120_000)
    assert too_big.status_code == 413
    uploads = (
        list(app.state.settings.upload_dir.glob("*"))
        if app.state.settings.upload_dir.exists()
        else []
    )
    assert uploads == []  # rejected files are not kept


def test_uploaded_filename_is_metadata_only(
    app: FastAPI, analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    response = _upload(analyst, synthetic_csv(40), "../../etc/<script>x.csv")
    assert response.status_code == 202
    run = db.get(DatasetAnalysisRun, response.json()["id"])
    assert run is not None
    assert run.original_filename == "_script_x.csv"
    stored = app.state.settings.upload_dir / run.stored_name
    assert stored.is_file() and stored.parent == app.state.settings.upload_dir


def test_file_missing_required_columns_fails_the_run_clearly(
    app: FastAPI, analyst: TestClient, registered_model: ModelVersion
) -> None:
    frame = synthetic_frame(synthetic_csv(60)).drop(columns=["sbytes"])
    run_id = _upload(analyst, frame.to_csv(index=False).encode()).json()["id"]
    run_queued_analyses(app)
    run = analyst.get(f"/api/v1/datasets/analyses/{run_id}").json()
    assert run["status"] == "failed"
    assert "sbytes" in run["error_message"]


def test_modified_model_file_is_never_used(
    app: FastAPI, analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    registered_model.artifact_sha256 = "0" * 64  # as if the file on disk had been replaced
    db.commit()
    run_id = _upload(analyst, synthetic_csv(40)).json()["id"]
    run_queued_analyses(app)
    run = analyst.get(f"/api/v1/datasets/analyses/{run_id}").json()
    assert run["status"] == "failed"
    assert "integrity" in run["error_message"]
    assert db.scalar(select(func.count()).select_from(Alert)) == 0


def test_interrupted_runs_are_marked_failed(
    app: FastAPI, analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    run_id = _upload(analyst, synthetic_csv(40)).json()["id"]
    run = db.get(DatasetAnalysisRun, run_id)
    assert run is not None
    run.status, run.started_at = "running", utcnow()
    db.commit()
    assert recover_interrupted(app.state.sessionmaker) == 1
    db.expire_all()
    assert db.get(DatasetAnalysisRun, run_id).status == "failed"  # type: ignore[union-attr]


def test_runs_listing_is_paginated(analyst: TestClient, registered_model: ModelVersion) -> None:
    for _ in range(3):
        _upload(analyst, synthetic_csv(40))
    page = analyst.get("/api/v1/datasets/analyses?page=1&page_size=2").json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["id"] > page["items"][1]["id"]  # newest first
