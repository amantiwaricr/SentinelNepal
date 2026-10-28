import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CIDR, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FIREWALL_OPEN_STATUSES, FIREWALL_OPERATIONS, FIREWALL_STATUSES, sql_in
from app.models.mixins import EMPTY_JSON_OBJECT, Timestamps

MIN_BLOCK_SECONDS = 60
MAX_BLOCK_SECONDS = 86_400


class FirewallRequest(Base, Timestamps):
    """A request to block an IP/CIDR temporarily. Nothing is applied without approval."""

    __tablename__ = "firewall_requests"
    __table_args__ = (
        CheckConstraint(sql_in("status", FIREWALL_STATUSES), name="status_valid"),
        CheckConstraint("ip_version IN (4, 6)", name="ip_version_valid"),
        CheckConstraint(
            f"duration_seconds BETWEEN {MIN_BLOCK_SECONDS} AND {MAX_BLOCK_SECONDS}",
            name="duration_range",
        ),
        # One open request per target at a time (prevents duplicate blocks).
        Index(
            "uq_firewall_requests_open_target",
            "target",
            unique=True,
            postgresql_where=text(sql_in("status", FIREWALL_OPEN_STATUSES)),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(CIDR)
    ip_version: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str] = mapped_column(Text)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FirewallActionResult(Base):
    """What the firewall helper reported for one operation (used from Phase 7)."""

    __tablename__ = "firewall_action_results"
    __table_args__ = (
        CheckConstraint(sql_in("operation", FIREWALL_OPERATIONS), name="operation_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("firewall_requests.id"), index=True)
    operation: Mapped[str] = mapped_column(String(16))
    success: Mapped[bool] = mapped_column(Boolean)
    helper_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    helper_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
