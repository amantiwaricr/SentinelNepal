"""ORM models. Import every model here so Alembic sees the complete metadata."""

from app.models.user import User

__all__ = ["User"]
