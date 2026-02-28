from datetime import date

from pydantic import field_validator, model_validator

from app.config.stats import EARLIEST_FILM_YEAR
from app.schemas.base_schema import BaseSchema


class Summary(BaseSchema):
    total_watches: int
    unique_titles: int
    total_rewatches: int
    total_minutes: int
    vote_average: float | None = None


class ByMethod(BaseSchema):
    cinema: int
    streaming: int
    home_video: int
    tv: int
    other: int


class Distribution(BaseSchema):
    by_method: ByMethod


class Pace(BaseSchema):
    on_track_for: int
    current_average: float
    days_since_last_log: int


class StatsRequest(BaseSchema):
    year_from: int | None = None
    year_to: int | None = None

    @field_validator("year_from", "year_to", mode="before")
    @classmethod
    def validate_year_bounds(cls, v: int | None) -> int | None:
        if v is not None:
            current_year = date.today().year
            if v < EARLIEST_FILM_YEAR or v > current_year:
                raise ValueError(f"Year must be between {EARLIEST_FILM_YEAR} and {current_year}")
        return v

    @model_validator(mode="after")
    def validate_year_pair(self) -> "StatsRequest":
        if (self.year_from is None) != (self.year_to is None):
            raise ValueError("yearFrom and yearTo must both be provided or both omitted")
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("yearFrom cannot be greater than yearTo")
        return self

    class Config:
        schema_extra = {"example": {"year_from": 2020, "year_to": 2023}}


class StatsResponse(BaseSchema):
    summary: Summary
    distribution: Distribution
    pace: Pace
