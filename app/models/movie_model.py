"""PostgreSQL movie ORM model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseEntity
from app.models.movie_provider_mapping_model import MovieProviderMapping


class Movie(BaseEntity):
    """Movie record stored in PostgreSQL."""

    __tablename__ = "movies"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    runtime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    providers: Mapped[list[MovieProviderMapping]] = relationship(lazy="raise")
