"""Pydantic models for Redis cache payloads."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CachedLog(BaseModel):
    """JSON-serializable mirror of ``Log`` columns for Redis payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    movie_id: UUID
    tmdb_id: int
    date_watched: datetime
    viewing_notes: str | None
    poster_path: str | None
    watched_where: str
    deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
