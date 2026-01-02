from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MovieRatingCreateUpdateRequest(BaseModel):
    """Schema for creating or updating a movie rating."""

    tmdbId: str = Field(..., description="Unique identifier of the movie")
    rating: int = Field(
        ..., ge=1, le=10, description="Rating given to the movie (1-10)"
    )
    comment: Optional[str] = Field(
        None, description="User's review or opinion about the movie"
    )


class MovieRatingResponse(BaseModel):
    """Schema for movie rating response."""

    id: str = Field(..., description="Unique identifier of the rating")
    userId: str = Field(..., description="Unique identifier of the user who rated")
    movieId: str = Field(..., description="Unique identifier of the movie")
    tmdbId: str = Field(..., description="Unique identifier of the movie")
    rating: int = Field(
        ..., ge=1, le=10, description="Rating given to the movie (1-10)"
    )
    comment: Optional[str] = Field(
        None, description="User's review or opinion about the movie"
    )
    createdAt: datetime = Field(
        ..., description="Timestamp when the rating was created"
    )
    updatedAt: datetime = Field(
        ..., description="Timestamp when the rating was last updated"
    )
