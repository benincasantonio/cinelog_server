from pydantic import ConfigDict, Field

from app.schemas.base_schemas import BaseSchema


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

    model_config = ConfigDict(json_schema_extra={"example": {"yearFrom": 2020, "yearTo": 2023}})


class StatsResponse(BaseSchema):
    summary: StatsSummary
    distribution: StatsDistribution
    pace: StatsPace


class UserStatsAggregate(BaseSchema):
    """Internal cross-table aggregate returned by the stats repository."""

    total_watches: int = 0
    unique_titles: int = 0
    total_minutes: int = 0
    vote_average: float | None = None
    by_method: StatsByMethod = Field(
        default_factory=lambda: StatsByMethod(cinema=0, streaming=0, home_video=0, tv=0, other=0)
    )
