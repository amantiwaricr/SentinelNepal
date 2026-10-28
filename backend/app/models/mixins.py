from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column

# Database-side defaults, so rows inserted outside the ORM get valid JSON too.
EMPTY_JSON_OBJECT = text("'{}'::jsonb")
EMPTY_JSON_ARRAY = text("'[]'::jsonb")


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Timestamps(CreatedAt):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
