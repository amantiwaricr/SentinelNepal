from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import EMPTY_JSON_OBJECT, CreatedAt


class ModelVersion(Base, CreatedAt):
    """A trained artifact registered for use. The SHA-256 here is the trusted value the
    artifact must match before it is ever loaded."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
        # At most one active model per feature profile.
        Index(
            "uq_model_versions_active_profile",
            "feature_profile",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(64))
    model_kind: Mapped[str] = mapped_column(String(32))
    feature_profile: Mapped[str] = mapped_column(String(32))
    artifact_dir: Mapped[str] = mapped_column(String(255))  # relative to MODEL_ARTIFACTS_DIR
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    features: Mapped[list[str]] = mapped_column(JSONB)
    class_labels: Mapped[list[str]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
    alert_threshold: Mapped[float | None] = mapped_column(Float)
    threshold_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    live_inference_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    registered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
