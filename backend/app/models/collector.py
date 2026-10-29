from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import COLLECTOR_MODES, sql_in
from app.models.mixins import EMPTY_JSON_OBJECT, CreatedAt


class Collector(Base, CreatedAt):
    """A live traffic collector. Starts in observation mode: its flows are counted and shown
    but not scored until an admin switches it to inference (behind the compatibility gate)."""

    __tablename__ = "collectors"
    __table_args__ = (CheckConstraint(sql_in("mode", COLLECTOR_MODES), name="mode_valid"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    # SHA-256 of the bearer token; the token itself is shown once, at creation.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    mode: Mapped[str] = mapped_column(String(16), default="observation")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_received: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    records_rejected: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    records_dropped: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_processed: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    alerts_created: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    # Counters reported by the collector itself in its heartbeat (packets read, malformed
    # TShark lines, capture files, send buffer size...).
    heartbeat_stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=EMPTY_JSON_OBJECT
    )
