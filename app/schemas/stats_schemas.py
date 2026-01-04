from pydantic import BaseModel


class Summary(BaseModel):
    total_watches: int
    unique_titles: int
    total_rewatches: int
    total_minutes: int


class ByMethod(BaseModel):
    cinema: int
    streaming: int
    home_video: int
    tv: int
    other: int


class Distribution(BaseModel):
    by_method: ByMethod


class Pace(BaseModel):
    on_track_for: int
    current_average: float
    days_since_last_log: int


class StatsRequest(BaseModel):
    yearFrom: int | None = None
    yearTo: int | None = None

    class Config:
        schema_extra = {"example": {"yearFrom": 2020, "yearTo": 2023}}


class StatsResponse(BaseModel):
    summary: Summary
    distribution: Distribution
    pace: Pace
