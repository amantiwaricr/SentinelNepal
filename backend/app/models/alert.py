from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import (
    ALERT_SOURCES,
    ALERT_STATUSES,
    PREDICTED_CATEGORIES,
    SEVERITIES,
    sql_in,
)
from app.models.mixins import EMPTY_JSON_OBJECT, Timestamps


class Alert(Base, Timestamps):
    """A model prediction that crossed the alert threshold. Evidence, not proof."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(sql_in("source", ALERT_SOURCES), name="source_valid"),
        CheckConstraint(sql_in("status", ALERT_STATUSES), name="status_valid"),
        CheckConstraint(sql_in("severity", SEVERITIES), name="severity_valid"),
        CheckConstraint(sql_in("predicted_category", PREDICTED_CATEGORIES), name="category_valid"),
        CheckConstraint("attack_score >= 0 AND attack_score <= 1", name="attack_score_range"),
        CheckConstraint("src_port IS NULL OR src_port BETWEEN 0 AND 65535", name="src_port_range"),
        CheckConstraint("dst_port IS NULL OR dst_port BETWEEN 0 AND 65535", name="dst_port_range"),
        Index("ix_alerts_status_severity", "status", "severity"),
        # GiST indexes make subnet queries (src_ip <<= '10.0.0.0/24') efficient.
        Index(
            "ix_alerts_src_ip",
            "src_ip",
            postgresql_using="gist",
            postgresql_ops={"src_ip": "inet_ops"},
        ),
        Index(
            "ix_alerts_dst_ip",
            "dst_ip",
            postgresql_using="gist",
            postgresql_ops={"dst_ip": "inet_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16))
    analysis_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataset_analysis_runs.id"), index=True
    )
    collector_id: Mapped[int | None] = mapped_column(ForeignKey("collectors.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    src_ip: Mapped[str | None] = mapped_column(INET)
    dst_ip: Mapped[str | None] = mapped_column(INET)
    src_port: Mapped[int | None] = mapped_column(Integer)
    dst_port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str | None] = mapped_column(String(32))
    service: Mapped[str | None] = mapped_column(String(32))
    predicted_category: Mapped[str] = mapped_column(String(32), index=True)
    attack_score: Mapped[float] = mapped_column(Float)  # 1 - score(Normal); uncalibrated
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="new")
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
    dedup_key: Mapped[str | None] = mapped_column(String(128), unique=True)


Index("ix_alerts_created_at", Alert.created_at)
