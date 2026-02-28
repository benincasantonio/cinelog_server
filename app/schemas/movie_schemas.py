from pydantic import Field
from datetime import date, datetime
from typing import Optional

from app.schemas.base_schema import BaseSchema


class MovieCreateRequest(BaseSchema):
    title: str = Field(
        ..., min_length=1, max_length=100, description="Title of the movie"
    )
    tmdb_id: int = Field(..., description="TMDB ID of the movie")


class MovieUpdateRequest(BaseSchema):
    title: str = Field(
        ..., min_length=1, max_length=100, description="Title of the movie"
    )


class MovieResponse(BaseSchema):
    id: str = Field(..., description="Unique identifier of the movie")
    title: str = Field(
        ..., min_length=1, max_length=100, description="Title of the movie"
    )
    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    poster_path: Optional[str] = Field(
        None, description="Path to the movie poster image"
    )
    release_date: Optional[date] = Field(None, description="Release date of the movie")
    overview: Optional[str] = Field(None, description="Overview/Synopsis of the movie")
    vote_average: Optional[float] = Field(None, description="Average vote rating")
    runtime: Optional[int] = Field(None, description="Runtime in minutes")
    original_language: Optional[str] = Field(None, description="Original language code")
    created_at: Optional[datetime] = Field(
        None, description="Creation date of the movie"
    )
    updated_at: Optional[datetime] = Field(
        None, description="Last update date of the movie"
    )
