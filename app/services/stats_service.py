from datetime import date
from uuid import UUID

from app.dependencies.repository_dependency import get_stats_repository
from app.repository.stats_repository_protocol import StatsRepositoryProtocol
from app.schemas.stats_schemas import (
    StatsDistribution,
    StatsPace,
    StatsResponse,
    StatsSummary,
)
from app.services.stats_cache_service import StatsCacheService


class StatsService:
    def __init__(
        self,
        stats_repository: StatsRepositoryProtocol | None = None,
        stats_cache_service: StatsCacheService | None = None,
    ):
        self.stats_repository = stats_repository or get_stats_repository()
        self.stats_cache_service = stats_cache_service or StatsCacheService()

    async def get_user_stats(
        self,
        user_id: UUID,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> StatsResponse:
        cached = await self.stats_cache_service.get_stats(user_id, year_from, year_to)
        if cached is not None:
            return cached

        date_from: date | None = date(year_from, 1, 1) if year_from is not None else None
        date_to: date | None = date(year_to, 12, 31) if year_to is not None else None

        stats = await self.stats_repository.get_user_stats(
            user_id,
            date_from=date_from,
            date_to=date_to,
        )

        result = StatsResponse(
            summary=StatsSummary(
                total_watches=stats.total_watches,
                unique_titles=stats.unique_titles,
                total_rewatches=max(0, stats.total_watches - stats.unique_titles),
                total_minutes=stats.total_minutes,
                vote_average=stats.vote_average,
            ),
            distribution=StatsDistribution(by_method=stats.by_method),
            pace=StatsPace(on_track_for=0, current_average=0.0, days_since_last_log=0),
        )

        await self.stats_cache_service.set_stats(user_id, year_from, year_to, stats=result)

        return result
