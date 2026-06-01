"""PostgreSQL movie-rating ORM model."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import PostgresBaseEntity


class PostgresMovieRating(PostgresBaseEntity):
    """Movie rating record stored in PostgreSQL."""

    __tablename__ = "movie_ratings"

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
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 10", name="ck_movie_ratings_rating_range"),
        UniqueConstraint("user_id", "tmdb_id", name="uq_movie_ratings_user_tmdb"),
        Index("ix_movie_ratings_user_movie", "user_id", "movie_id"),
    )
