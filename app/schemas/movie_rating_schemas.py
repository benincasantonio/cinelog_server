from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MovieRatingCreateRequest(BaseModel):
    """Schema for creating or updating a movie rating."""
    movieId: str = Field(..., description="Unique identifier of the movie")
    rating: int = Field(..., ge=1, le=10, description="Rating given to the movie (1-10)")
    comment: Optional[str] = Field(None, description="User's review or opinion about the movie")


class MovieRatingUpdateRequest(BaseModel):
    """Schema for updating an existing movie rating."""
    rating: Optional[int] = Field(None, ge=1, le=10, description="Rating given to the movie (1-10)")
    comment: Optional[str] = Field(None, description="User's review or opinion about the movie")


class MovieRatingResponse(BaseModel):
    """Schema for movie rating response."""
    id: str = Field(..., description="Unique identifier of the rating")
    userId: str = Field(..., description="Unique identifier of the user who rated")
    movieId: str = Field(..., description="Unique identifier of the movie")
    rating: int = Field(..., ge=1, le=10, description="Rating given to the movie (1-10)")
    comment: Optional[str] = Field(None, description="User's review or opinion about the movie")
    createdAt: datetime = Field(..., description="Timestamp when the rating was created")
    updatedAt: datetime = Field(..., description="Timestamp when the rating was last updated")
