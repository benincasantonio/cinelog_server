from beanie import PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_entity import BaseEntity


class MovieRating(BaseEntity):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId)
    movie_id: PydanticObjectId = Field(alias="movieId")
    review: str | None = None
    rating: int | None = Field(default=None, ge=1, le=10)
    user_id: PydanticObjectId = Field(alias="userId")
    tmdb_id: int = Field(alias="tmdbId")

    class Settings:
        name = "movie_ratings"
        indexes = [
            IndexModel([("createdAt", DESCENDING)]),
            IndexModel([("deleted", ASCENDING)]),
            IndexModel([("movieId", ASCENDING)]),
            IndexModel([("rating", ASCENDING)]),
            IndexModel([("tmdbId", ASCENDING)]),
            IndexModel([("userId", ASCENDING), ("tmdbId", ASCENDING)], unique=True),
        ]
