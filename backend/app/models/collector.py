from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import COLLECTOR_MODES, sql_in
from app.models.mixins import CreatedAt


class Collector(Base, CreatedAt):
    """A live traffic collector (used from Phase 6). Starts in observation-only mode."""

    __tablename__ = "collectors"
    __table_args__ = (CheckConstraint(sql_in("mode", COLLECTOR_MODES), name="mode_valid"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16), default="observation")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_received: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    records_rejected: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    records_dropped: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
