from pydantic import BaseModel, EmailStr, Field
from datetime import date


class MovieCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")


class MovieUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")

class MovieResponse(BaseModel):
    id: str = Field(..., description="Unique identifier of the movie")
    title: str = Field(..., min_length=1, max_length=100, description="Title of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")
    createdAt: date = Field(..., description="Creation date of the movie")
    updatedAt: date = Field(..., description="Last update date of the movie")
