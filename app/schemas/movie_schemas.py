from datetime import date, datetime

from beanie import PydanticObjectId
from pydantic import Field

from app.schemas.base_schemas import BaseSchema


class MovieCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")
    tmdb_id: int = Field(..., description="TMDB ID of the movie")


class MovieUpdateRequest(BaseSchema):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")


class MovieResponse(BaseSchema):
    id: PydanticObjectId = Field(..., description="Unique identifier of the movie")
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")
    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    poster_path: str | None = Field(None, description="Path to the movie poster image")
    release_date: date | None = Field(None, description="Release date of the movie")
    overview: str | None = Field(None, description="Overview/Synopsis of the movie")
    vote_average: float | None = Field(None, description="Average vote rating")
    runtime: int | None = Field(None, description="Runtime in minutes")
    original_language: str | None = Field(None, description="Original language code")
    created_at: datetime | None = Field(None, description="Creation date of the movie")
    updated_at: datetime | None = Field(None, description="Last update date of the movie")


class MovieStats(BaseSchema):
    total_runtime: int = Field(0, description="Total runtime of the movie in minutes")
