from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy import func, select

from app.api.deps import AnalystUser, AppSettings, Audit, DbSession
from app.core.errors import AppError
from app.models.analysis import DatasetAnalysisRun
from app.schemas.common import Page, PageParams, page_params
from app.schemas.ops import AnalysisRunOut
from app.services import analyses

router = APIRouter(prefix="/datasets/analyses", tags=["datasets"])
MULTIPART_OVERHEAD = 1024 * 1024


@router.post("", response_model=AnalysisRunOut, status_code=202)
def upload_dataset(
    file: UploadFile,
    request: Request,
    ctx: Audit,
    db: DbSession,
    settings: AppSettings,
) -> AnalysisRunOut:
    """Upload a UNSW-NB15-format CSV; it is analysed in the background (poll its status)."""
    declared = request.headers.get("content-length")
    limit = settings.max_upload_mb * 1024 * 1024 + MULTIPART_OVERHEAD
    if declared and declared.isdigit() and int(declared) > limit:
        raise AppError(
            "payload_too_large", f"File exceeds the {settings.max_upload_mb} MB upload limit", 413
        )
    run = analyses.store_upload(db, settings, ctx, file.filename, file.file)
    return AnalysisRunOut.model_validate(run)


@router.get("", response_model=Page[AnalysisRunOut])
def list_runs(
    _: AnalystUser, db: DbSession, paging: Annotated[PageParams, Depends(page_params)]
) -> Page[AnalysisRunOut]:
    total = db.scalar(select(func.count()).select_from(DatasetAnalysisRun)) or 0
    rows = db.scalars(
        select(DatasetAnalysisRun)
        .order_by(DatasetAnalysisRun.id.desc())
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[AnalysisRunOut.model_validate(r) for r in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.get("/{run_id}", response_model=AnalysisRunOut)
def get_run(run_id: int, _: AnalystUser, db: DbSession) -> AnalysisRunOut:
    run = db.get(DatasetAnalysisRun, run_id)
    if run is None:
        raise AppError("not_found", "Analysis run not found", 404)
    return AnalysisRunOut.model_validate(run)
