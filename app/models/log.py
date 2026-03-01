from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_entity import BaseEntity


class Log(BaseEntity):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId)
    user_id: PydanticObjectId = Field(alias="userId")
    movie_id: PydanticObjectId = Field(alias="movieId")
    tmdb_id: int = Field(alias="tmdbId")
    date_watched: datetime = Field(alias="dateWatched")
    viewing_notes: str | None = Field(default=None, alias="viewingNotes")
    poster_path: str | None = Field(default=None, alias="posterPath")
    watched_where: Literal["cinema", "streaming", "homeVideo", "tv", "other"] = Field(
        default="other",
        alias="watchedWhere",
    )

    class Settings:
        name = "logs"
        indexes = [
            IndexModel([("createdAt", DESCENDING)]),
            IndexModel([("deleted", ASCENDING)]),
            IndexModel([("userId", ASCENDING)]),
            IndexModel([("dateWatched", ASCENDING)]),
            IndexModel([("userId", ASCENDING), ("dateWatched", DESCENDING)]),
            IndexModel(
                [
                    ("userId", ASCENDING),
                    ("dateWatched", DESCENDING),
                    ("createdAt", DESCENDING),
                ]
            ),
            IndexModel([("userId", ASCENDING), ("movieId", ASCENDING)]),
            IndexModel([("tmdbId", ASCENDING), ("dateWatched", DESCENDING)]),
            IndexModel([("watchedWhere", ASCENDING)]),
            IndexModel(
                [
                    ("userId", ASCENDING),
                    ("watchedWhere", ASCENDING),
                    ("createdAt", ASCENDING),
                ]
            ),
        ]
