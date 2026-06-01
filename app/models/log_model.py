"""PostgreSQL log ORM model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import PostgresBaseEntity
from app.types import WATCHED_WHERE_CHOICES


class PostgresLog(PostgresBaseEntity):
    """Viewing log record stored in PostgreSQL."""

    __tablename__ = "logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    movie_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("movies.id"),
        nullable=False,
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date_watched: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    viewing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    watched_where: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'other'"),
        default="other",
    )

    _watched_where_sql = ", ".join(f"'{choice}'" for choice in WATCHED_WHERE_CHOICES)

    __table_args__ = (
        CheckConstraint(
            f"watched_where IN ({_watched_where_sql})",
            name="ck_logs_watched_where",
        ),
        Index("ix_logs_user_date_watched", "user_id", text("date_watched DESC")),
        Index(
            "ix_logs_user_date_watched_created_at",
            "user_id",
            text("date_watched DESC"),
            text("created_at DESC"),
        ),
        Index("ix_logs_user_movie", "user_id", "movie_id"),
        Index("ix_logs_tmdb_date_watched", "tmdb_id", text("date_watched DESC")),
        Index("ix_logs_user_watched_where_created_at", "user_id", "watched_where", "created_at"),
    )
