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

    class Config:
        schema_extra = {"example": {"year_from": 2020, "year_to": 2023}}


class StatsResponse(BaseSchema):
    summary: Summary
    distribution: Distribution
    pace: Pace
