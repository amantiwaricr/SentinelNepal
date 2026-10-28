"""Dataset uploads and their analysis by the active dataset-analysis model."""

import hashlib
import logging
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import BinaryIO

from sentinel_ml.features.cleaning import SchemaError
from sentinel_ml.features.dataset import DatasetError, detect_schema, iter_raw_chunks
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.models.alert import Alert
from app.models.analysis import DatasetAnalysisRun
from app.services import audit
from app.services.alerts import alert_from_prediction, should_alert
from app.services.audit import AuditContext
from app.services.ml_service import ModelUnavailableError, PredictorCache
from app.services.models import active_model

logger = logging.getLogger(__name__)

CHUNK_BYTES = 1 << 20
CHUNK_ROWS = 5_000  # below the Predictor's per-call limit
SNIFF_BYTES = 64 * 1024
_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9._ ()-]")


def safe_display_name(filename: str | None) -> str:
    """Keep the uploaded name only as display metadata: basename, safe characters only."""
    name = Path((filename or "upload.csv").replace("\\", "/")).name
    return _UNSAFE_NAME_CHARS.sub("_", name)[:255] or "upload.csv"


def _looks_like_csv(head: bytes) -> bool:
    if not head.strip() or b"\x00" in head:
        return False
    text = head.decode("utf-8", errors="replace")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return first_line.count(",") >= 5


def store_upload(
    db: Session,
    settings: Settings,
    ctx: AuditContext,
    filename: str | None,
    stream: BinaryIO,
) -> DatasetAnalysisRun:
    """Stream an upload to disk under a server-generated name and queue it for analysis."""
    display_name = safe_display_name(filename)
    if not display_name.lower().endswith(".csv"):
        raise AppError("unsupported_media_type", "Only .csv files are accepted", 415)
    if active_model(db, settings.dataset_model_profile) is None:
        raise ModelUnavailableError("No active dataset-analysis model is registered")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.csv"
    target = settings.upload_dir / stored_name
    limit = settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    head = b""
    try:
        with target.open("wb") as handle:
            while chunk := stream.read(CHUNK_BYTES):
                size += len(chunk)
                if size > limit:
                    raise AppError(
                        "payload_too_large",
                        f"File exceeds the {settings.max_upload_mb} MB upload limit",
                        413,
                    )
                if len(head) < SNIFF_BYTES:
                    head += chunk[: SNIFF_BYTES - len(head)]
                digest.update(chunk)
                handle.write(chunk)
        if size == 0 or not _looks_like_csv(head):
            raise AppError("invalid_file", "The file does not look like a CSV dataset", 422)
    except BaseException:
        target.unlink(missing_ok=True)
        raise

    run = DatasetAnalysisRun(
        uploaded_by=ctx.actor.id if ctx.actor else None,
        original_filename=display_name,
        stored_name=stored_name,
        file_sha256=digest.hexdigest(),
        size_bytes=size,
        status="queued",
    )
    db.add(run)
    db.flush()
    audit.record(
        db,
        ctx,
        "dataset.uploaded",
        target_type="analysis_run",
        target_id=run.id,
        details={"filename": display_name, "size_bytes": size, "sha256": run.file_sha256},
    )
    db.commit()
    return run


def recover_interrupted(factory: sessionmaker[Session]) -> int:
    """Runs left 'running' by a crash or restart are marked failed, never silently lost."""
    with factory() as db:
        result = db.execute(
            update(DatasetAnalysisRun)
            .where(DatasetAnalysisRun.status == "running")
            .values(
                status="failed",
                finished_at=utcnow(),
                error_message="Interrupted by a server restart; upload the file again",
            )
        )
        db.commit()
        return int(result.rowcount)  # type: ignore[attr-defined]


def claim_next_run(db: Session) -> DatasetAnalysisRun | None:
    run = db.scalar(
        select(DatasetAnalysisRun)
        .where(DatasetAnalysisRun.status == "queued")
        .order_by(DatasetAnalysisRun.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if run is not None:
        run.status = "running"
        run.started_at = utcnow()
        db.commit()
    return run


def process_next_run(
    factory: sessionmaker[Session], settings: Settings, predictors: PredictorCache
) -> bool:
    """Analyse the oldest queued run. Returns False when the queue is empty."""
    with factory() as db:
        run = claim_next_run(db)
        if run is None:
            return False
        try:
            _analyse(db, settings, predictors, run)
        except (AppError, DatasetError, SchemaError) as exc:
            db.rollback()
            _fail(db, run, exc.message if isinstance(exc, AppError) else str(exc))
        except Exception:
            logger.exception("Analysis run %s failed unexpectedly", run.id)
            db.rollback()
            _fail(db, run, "Internal error during analysis; see the server log")
        return True


def _fail(db: Session, run: DatasetAnalysisRun, message: str) -> None:
    run = db.merge(run)
    run.status = "failed"
    run.error_message = message[:2000]
    run.finished_at = utcnow()
    audit.record(
        db,
        AuditContext.system("analysis-worker"),
        "dataset.analysis.failed",
        target_type="analysis_run",
        target_id=run.id,
        outcome="failure",
        details={"error": run.error_message},
    )
    db.commit()


def _analyse(
    db: Session, settings: Settings, predictors: PredictorCache, run: DatasetAnalysisRun
) -> None:
    model = active_model(db, settings.dataset_model_profile)
    if model is None:
        raise ModelUnavailableError("No active dataset-analysis model is registered")
    predictor = predictors.get(model)
    path = settings.upload_dir / run.stored_name
    kind = detect_schema(path)
    run.detected_schema = kind
    run.model_version_id = model.id

    predicted: Counter[str] = Counter()
    alerted: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    rows_with_ip = 0
    suppressed = 0
    offset = 0
    for chunk in iter_raw_chunks(path, kind, None, chunk_rows=CHUNK_ROWS):
        batch = predictor.predict_frame(chunk)
        for rejected in batch.rejected:
            rejections.update(rejected.reasons)
        new_alerts: list[Alert] = []
        for prediction in batch.predictions:
            predicted[prediction.predicted_category] += 1
            if prediction.metadata.get("src_ip") or prediction.metadata.get("dst_ip"):
                rows_with_ip += 1
            if not should_alert(prediction, model.alert_threshold):
                continue
            if run.alerts_created + len(new_alerts) >= settings.max_alerts_per_run:
                suppressed += 1
                continue
            alert = alert_from_prediction(
                prediction,
                model,
                source="dataset",
                dedup_key=f"dataset:{run.id}:{offset + prediction.index}",
                analysis_run_id=run.id,
            )
            alerted[alert.predicted_category] += 1
            new_alerts.append(alert)
        db.add_all(new_alerts)
        offset += len(chunk)
        run.rows_total = offset
        run.rows_valid += len(batch.predictions)
        run.rows_rejected += len(batch.rejected)
        run.alerts_created += len(new_alerts)
        db.commit()  # progress becomes visible to the API after every chunk

    if offset == 0:
        raise AppError("invalid_file", "The file contains no data rows", 422)
    run.summary = {
        "model": {"id": model.id, "name": model.name, "version": model.version},
        "alert_rule": (
            f"attack score >= {model.alert_threshold:.6f} (chosen on the validation split)"
            if model.alert_threshold is not None
            else "default decision: highest-scoring class is an attack"
        ),
        "predicted_class_counts": dict(predicted.most_common()),
        "alerts_by_category": dict(alerted.most_common()),
        "alerts_suppressed_over_cap": suppressed,
        "rejection_reasons": dict(rejections.most_common(20)),
        "rows_with_ip_metadata": rows_with_ip,
        "note": "Predicted classes are model output, not confirmed attacks. Any label "
        "columns in the file were ignored.",
    }
    run.status = "completed"
    run.finished_at = utcnow()
    audit.record(
        db,
        AuditContext.system("analysis-worker"),
        "dataset.analysis.completed",
        target_type="analysis_run",
        target_id=run.id,
        details={"rows": run.rows_total, "alerts": run.alerts_created, "model_id": model.id},
    )
    db.commit()
