from datetime import datetime

from pydantic import Field

from app.schemas.base_schemas import BaseSchema
from app.types import RatingInt


class MovieRatingCreateUpdateRequest(BaseSchema):
    """Schema for creating or updating a movie rating."""

    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    rating: RatingInt = Field(..., description="Rating given to the movie (1-10)")
    comment: str | None = Field(None, description="User's review or opinion about the movie")


class MovieRatingResponse(BaseSchema):
    """Schema for movie rating response."""

    id: str = Field(..., description="Unique identifier of the rating")
    user_id: str = Field(..., description="Unique identifier of the user who rated")
    movie_id: str = Field(..., description="Unique identifier of the movie")
    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    rating: RatingInt = Field(..., description="Rating given to the movie (1-10)")
    comment: str | None = Field(None, description="User's review or opinion about the movie")
    created_at: datetime = Field(..., description="Timestamp when the rating was created")
    updated_at: datetime = Field(..., description="Timestamp when the rating was last updated")
