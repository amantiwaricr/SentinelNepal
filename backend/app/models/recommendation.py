from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import EMPTY_JSON_ARRAY, EMPTY_JSON_OBJECT, CreatedAt


class Recommendation(Base, CreatedAt):
    """A rule-based defensive suggestion for one alert (rules: services/recommendations)."""

    __tablename__ = "recommendations"
    # One row per rule per alert: generation is idempotent even when two requests race.
    __table_args__ = (
        UniqueConstraint("alert_id", "rule_id", name="uq_recommendations_alert_rule"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(64))
    rule_version: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    required_evidence: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=EMPTY_JSON_ARRAY
    )
    evidence_present: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
    priority: Mapped[str] = mapped_column(String(16))
    limitations: Mapped[str] = mapped_column(Text)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)
