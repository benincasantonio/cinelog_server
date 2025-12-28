from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class MovieCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")


class MovieUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")

class MovieResponse(BaseModel):
    id: str = Field(..., description="Unique identifier of the movie")
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")
    posterPath: Optional[str] = Field(None, description="Path to the movie poster image")
    releaseDate: Optional[date] = Field(None, description="Release date of the movie")
    overview: Optional[str] = Field(None, description="Overview/Synopsis of the movie")
    voteAverage: Optional[float] = Field(None, description="Average vote rating")
    runtime: Optional[int] = Field(None, description="Runtime in minutes")
    originalLanguage: Optional[str] = Field(None, description="Original language code")
    createdAt: Optional[date] = Field(None, description="Creation date of the movie")
    updatedAt: Optional[date] = Field(None, description="Last update date of the movie")
