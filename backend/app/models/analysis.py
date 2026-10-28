from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ANALYSIS_STATUSES, sql_in
from app.models.mixins import EMPTY_JSON_OBJECT, CreatedAt


class DatasetAnalysisRun(Base, CreatedAt):
    """One uploaded CSV and the result of scoring it with the active dataset-analysis model."""

    __tablename__ = "dataset_analysis_runs"
    __table_args__ = (CheckConstraint(sql_in("status", ANALYSIS_STATUSES), name="status_valid"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)  # server-generated
    file_sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    detected_schema: Mapped[str | None] = mapped_column(String(32))
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    rows_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_valid: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    alerts_created: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
