from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import INCIDENT_STATUSES, SEVERITIES, sql_in
from app.models.mixins import CreatedAt, Timestamps

MAX_NOTE_LENGTH = 10_000


class Incident(Base, Timestamps):
    """An analyst-managed investigation. Only people change its status."""

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(sql_in("status", INCIDENT_STATUSES), name="status_valid"),
        CheckConstraint(sql_in("severity", SEVERITIES), name="severity_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IncidentAlert(Base):
    __tablename__ = "incident_alerts"

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True
    )
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), primary_key=True, index=True)
    linked_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvestigationNote(Base, CreatedAt):
    """Append-only: there is no endpoint to edit or delete a note."""

    __tablename__ = "investigation_notes"
    __table_args__ = (
        CheckConstraint(f"char_length(body) BETWEEN 1 AND {MAX_NOTE_LENGTH}", name="body_length"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
