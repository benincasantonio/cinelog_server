"""SQLAlchemy declarative base and shared entity fields for PostgreSQL models."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, ColumnElement, DateTime, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for PostgreSQL ORM models."""


class PostgresBaseEntity(Base):
    """Abstract PostgreSQL base entity matching common Mongo lifecycle fields."""

    __abstract__ = True

    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"), default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @classmethod
    def active(cls) -> ColumnElement[bool]:
        """Return a WHERE criterion that excludes soft-deleted rows."""
        return cls.deleted.is_(False)
