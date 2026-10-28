from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AUDIT_ACTOR_TYPES, AUDIT_OUTCOMES, sql_in
from app.models.mixins import EMPTY_JSON_OBJECT


class AuditLog(Base):
    """Append-only security audit trail. A database trigger rejects UPDATE, DELETE and
    TRUNCATE, and no API endpoint modifies it."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(sql_in("actor_type", AUDIT_ACTOR_TYPES), name="actor_type_valid"),
        CheckConstraint(sql_in("outcome", AUDIT_OUTCOMES), name="outcome_valid"),
        Index("ix_audit_logs_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_label: Mapped[str | None] = mapped_column(String(64))  # username at the time
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16))
    ip_address: Mapped[str | None] = mapped_column(INET)
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
