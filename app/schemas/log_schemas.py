from typing import Optional

from pydantic import BaseModel, Field
from datetime import date

from pydantic.v1 import validator, root_validator


class LogCreateRequest(BaseModel):
    movieId: str = Field(..., description="Unique identifier of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")
    dateWatched: date = Field(..., description="Date when the movie was watched")
    comment: str = Field(None, description="Optional comment about the movie")
    rating: int = Field(None, ge=1, le=10, description="Rating given to the movie (1-10)")
    posterPath: str = Field(None, description="Path to the movie poster image")
    watchedWhere: str = Field(None, description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)")

    @validator('watchedWhere')
    def validate_watched_where(self, value):
        valid_choices = ["cinema", "streaming", "homeVideo", "tv", "other"]

        if value not in valid_choices:
            raise ValueError(f"watchedWhere must be one of {valid_choices}")

        return value


class LogCreateResponse(BaseModel):
    id: str = Field(..., description="Unique identifier of the log entry")
    movieId: str = Field(..., description="Unique identifier of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")
    dateWatched: date = Field(..., description="Date when the movie was watched")
    comment: str = Field(None, description="Optional comment about the movie")
    rating: int = Field(None, ge=1, le=10, description="Rating given to the movie (1-10)")
    posterPath: str = Field(None, description="Path to the movie poster image")
    watchedWhere: str = Field(None, description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)")


class LogListItem(BaseModel):
    id: str = Field(..., description="Unique identifier of the log entry")
    movieId: str = Field(..., description="Unique identifier of the movie")
    tmdbId: int = Field(..., description="TMDB ID of the movie")
    dateWatched: date = Field(..., description="Date when the movie was watched")
    comment: str = Field(None, description="Optional comment about the movie")
    rating: int = Field(None, ge=1, le=10, description="Rating given to the movie (1-10)")
    posterPath: str = Field(None, description="Path to the movie poster image")
    watchedWhere: str = Field(None, description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)")
    timeWatched: int = Field(..., description="Time in seconds when the movie was watched")


class LogListResponse(BaseModel):
    logs: list[LogListItem] = Field(..., description="List of log entries")
    totalCount: int = Field(..., description="Total number of log entries")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Number of log entries per page")


class LogListRequest(BaseModel):
    page: int = Field(1, ge=1, description="Page number for pagination")
    pageSize: int = Field(10, ge=1, le=100, description="Number of log entries per page")
    sortBy: str = Field(None, description="Field to sort by (e.g., dateWatched, rating)")
    sortOrder: str = Field("desc", description="Sort order (asc or desc)")
    watchedWhere: Optional[str] = Field(None, description="Filter logs by where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)")
    dateWatchedFrom: Optional[date] = Field(None, description="Filter logs by date watched from")
    dateWatchedTo: Optional[date] = Field(None, description="Filter logs by date watched to")

    @root_validator
    def validate_dates(cls, values):
        if not values.get('dateWatchedFrom') and not values.get('dateWatchedTo'):
            return values

        date_from = values.get('dateWatchedFrom')
        date_to = values.get('dateWatchedTo')

        if date_from and date_to and date_from > date_to:
            raise ValueError("dateWatchedFrom cannot be after dateWatchedTo")

        return values

    @validator('sortBy')
    def validate_sort_by(cls, value):
        valid_fields = ["dateWatched", "rating"]
        if value and value not in valid_fields:
            raise ValueError(f"sortBy must be one of {valid_fields}")
        return value

    @validator('sortOrder')
    def validate_sort_order(cls, value):
        if value not in ["asc", "desc"]:
            raise ValueError("sortOrder must be either 'asc' or 'desc'")
        return value

    @validator('watchedWhere')
    def validate_watched_where(cls, value):
        if value is None:
            return value

        valid_choices = ["cinema", "streaming", "homeVideo", "tv", "other"]
        if value and value not in valid_choices:
            raise ValueError(f"watchedWhere must be one of {valid_choices}")
        return value



