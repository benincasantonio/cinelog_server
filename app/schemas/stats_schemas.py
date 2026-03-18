from typing import Literal

from beanie import PydanticObjectId

from app.schemas.base_schema import BaseSchema


class StatsSummary(BaseSchema):
    total_watches: int
    unique_titles: int
    total_rewatches: int
    total_minutes: int
    vote_average: float | None = None


class StatsByMethod(BaseSchema):
    cinema: int
    streaming: int
    home_video: int
    tv: int
    other: int


class StatsDistribution(BaseSchema):
    by_method: StatsByMethod


class StatsPace(BaseSchema):
    on_track_for: int
    current_average: float
    days_since_last_log: int


class StatsRequest(BaseSchema):
    year_from: int | None = None
    year_to: int | None = None

    class Config:
        schema_extra = {"example": {"year_from": 2020, "year_to": 2023}}


class StatsResponse(BaseSchema):
    summary: StatsSummary
    distribution: StatsDistribution
    pace: StatsPace


class LogDistributionEntry(BaseSchema):
    watched_where: Literal["cinema", "streaming", "homeVideo", "tv", "other"] | None = (
        None
    )
    count: int = 0


class LogStats(BaseSchema):
    total_watches: int = 0
    unique_titles: int = 0
    unique_movie_ids: list[PydanticObjectId] = []
    distribution: list[LogDistributionEntry] = []
