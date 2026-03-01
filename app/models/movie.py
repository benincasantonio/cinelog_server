from datetime import datetime
from bson import ObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_entity import BaseEntity


class Movie(BaseEntity):
    id: str = Field(default_factory=lambda: str(ObjectId()))  # type: ignore[assignment]
    tmdb_id: int = Field(alias="tmdbId")
    title: str
    release_date: datetime | None = Field(default=None, alias="releaseDate")
    overview: str | None = None
    poster_path: str | None = Field(default=None, alias="posterPath")
    vote_average: float | None = Field(default=None, alias="voteAverage")
    runtime: int | None = None
    original_language: str | None = Field(default=None, alias="originalLanguage")

    class Settings:
        name = "movies"
        indexes = [
            IndexModel([("createdAt", DESCENDING)]),
            IndexModel([("deleted", ASCENDING)]),
            IndexModel([("tmdbId", ASCENDING)], unique=True),
        ]
