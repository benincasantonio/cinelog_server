from typing import Optional

from pydantic import Field, field_validator, model_validator
from datetime import date

from app.schemas.base_schema import BaseSchema
from app.schemas.movie_schemas import MovieResponse


class LogCreateRequest(BaseSchema):
    movie_id: Optional[str] = Field(
        None, description="Unique identifier of the movie (auto-generated from tmdbId)"
    )
    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    date_watched: date = Field(..., description="Date when the movie was watched")
    viewing_notes: Optional[str] = Field(
        None, description="Optional notes about this viewing"
    )
    poster_path: Optional[str] = Field(
        None,
        description="Path to the movie poster image (auto-fetched from TMDB if not provided)",
    )
    watched_where: str = Field(
        "other",
        description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)",
    )

    @field_validator("watched_where")
    @classmethod
    def validate_watched_where(cls, value):
        valid_choices = ["cinema", "streaming", "homeVideo", "tv", "other"]

        if value not in valid_choices:
            raise ValueError(f"watched_where must be one of {valid_choices}")

        return value


class LogCreateResponse(BaseSchema):
    id: str = Field(..., description="Unique identifier of the log entry")
    movie_id: str = Field(..., description="Unique identifier of the movie")
    movie: MovieResponse = Field(..., description="Details of the movie")
    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    date_watched: date = Field(..., description="Date when the movie was watched")
    viewing_notes: Optional[str] = Field(
        None, description="Optional notes about this viewing"
    )
    poster_path: Optional[str] = Field(
        None, description="Path to the movie poster image"
    )
    watched_where: Optional[str] = Field(
        None,
        description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)",
    )


class LogUpdateRequest(BaseSchema):
    """Schema for updating an existing log entry."""

    date_watched: Optional[date] = Field(
        None, description="Date when the movie was watched"
    )
    viewing_notes: Optional[str] = Field(
        None, description="Optional notes about this viewing"
    )
    watched_where: Optional[str] = Field(
        None,
        description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)",
    )

    @field_validator("watched_where")
    @classmethod
    def validate_watched_where(cls, value):
        if value is None:
            return value
        valid_choices = ["cinema", "streaming", "homeVideo", "tv", "other"]
        if value not in valid_choices:
            raise ValueError(f"watched_where must be one of {valid_choices}")
        return value


class LogListItem(BaseSchema):
    id: str = Field(..., description="Unique identifier of the log entry")
    movie_id: str = Field(..., description="Unique identifier of the movie")
    movie: MovieResponse = Field(..., description="Details of the movie")
    tmdb_id: int = Field(..., description="TMDB ID of the movie")
    date_watched: date = Field(..., description="Date when the movie was watched")
    viewing_notes: Optional[str] = Field(
        None, description="Optional notes about this viewing"
    )
    poster_path: Optional[str] = Field(
        None, description="Path to the movie poster image"
    )
    watched_where: Optional[str] = Field(
        None,
        description="Where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)",
    )
    movie_rating: Optional[int] = Field(
        None, description="User rating for the movie (if available)"
    )


class LogListResponse(BaseSchema):
    logs: list[LogListItem] = Field(..., description="List of log entries")


class LogListRequest(BaseSchema):
    sort_by: str = Field(
        "dateWatched", description="Field to sort by (e.g., dateWatched)"
    )
    sort_order: str = Field("desc", description="Sort order (asc or desc)")
    watched_where: Optional[str] = Field(
        None,
        description="Filter logs by where the movie was watched (e.g., Cinema, Home Video, Streaming etc.)",
    )
    date_watched_from: Optional[date] = Field(
        None, description="Filter logs by date watched from"
    )
    date_watched_to: Optional[date] = Field(
        None, description="Filter logs by date watched to"
    )

    @model_validator(mode="after")
    def validate_dates(self):
        if not self.date_watched_from and not self.date_watched_to:
            return self

        date_from = self.date_watched_from
        date_to = self.date_watched_to

        if date_from and date_to and date_from > date_to:
            raise ValueError("date_watched_from cannot be after date_watched_to")

        return self

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value):
        valid_fields = ["dateWatched", "watchedWhere"]
        if value and value not in valid_fields:
            raise ValueError(f"sort_by must be one of {valid_fields}")
        return value

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value):
        if value not in ["asc", "desc"]:
            raise ValueError("sort_order must be either 'asc' or 'desc'")
        return value

    @field_validator("watched_where")
    @classmethod
    def validate_watched_where(cls, value):
        if value is None:
            return value

        valid_choices = ["cinema", "streaming", "homeVideo", "tv", "other"]
        if value and value not in valid_choices:
            raise ValueError(f"watched_where must be one of {valid_choices}")
        return value
