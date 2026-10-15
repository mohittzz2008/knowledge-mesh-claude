"""SQLAlchemy 2.x Declarative Base for Knowledge Mesh Data Models."""

from datetime import datetime, timezone
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models with standard timestamp fields."""

    pass


def utc_now() -> datetime:
    """Helper to return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)
