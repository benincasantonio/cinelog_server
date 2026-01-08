from typing import Optional
from pydantic import Field
from datetime import datetime

from app.schemas.base_schema import BaseSchema


class MovieRatingCreateUpdateRequest(BaseSchema):
    """Schema for creating or updating a movie rating."""

    tmdb_id: str = Field(..., description="Unique identifier of the movie")
    rating: int = Field(
        ..., ge=1, le=10, description="Rating given to the movie (1-10)"
    )
    comment: Optional[str] = Field(
        None, description="User's review or opinion about the movie"
    )


class MovieRatingResponse(BaseSchema):
    """Schema for movie rating response."""

    id: str = Field(..., description="Unique identifier of the rating")
    user_id: str = Field(..., description="Unique identifier of the user who rated")
    movie_id: str = Field(..., description="Unique identifier of the movie")
    tmdb_id: str = Field(..., description="Unique identifier of the movie")
    rating: int = Field(
        ..., ge=1, le=10, description="Rating given to the movie (1-10)"
    )
    comment: Optional[str] = Field(
        None, description="User's review or opinion about the movie"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the rating was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the rating was last updated"
    )
