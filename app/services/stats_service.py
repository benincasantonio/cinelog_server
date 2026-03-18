import asyncio
from datetime import date

from beanie import PydanticObjectId

from app.repository.log_repository import LogRepository
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.schemas.stats_schemas import (
    LogStats,
    StatsByMethod,
    StatsDistribution,
    StatsPace,
    StatsResponse,
    StatsSummary,
)


class StatsService:
    def __init__(
        self,
        log_repository: LogRepository | None = None,
        movie_rating_repository: MovieRatingRepository | None = None,
        movie_repository: MovieRepository | None = None,
    ):
        self.log_repository = log_repository or LogRepository()
        self.movie_rating_repository = (
            movie_rating_repository or MovieRatingRepository()
        )
        self.movie_repository = movie_repository or MovieRepository()

    async def get_user_stats(
        self,
        user_id: PydanticObjectId,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> StatsResponse:
        date_from: date | None = (
            date(year_from, 1, 1) if year_from is not None else None
        )
        date_to: date | None = date(year_to, 12, 31) if year_to is not None else None

        log_stats: LogStats = await self.log_repository.get_log_stats(
            user_id,
            date_from=date_from,
            date_to=date_to,
        )

        movie_ids = set(log_stats.unique_movie_ids)

        movie_rating_stats, movie_stats = await asyncio.gather(
            self.movie_rating_repository.get_user_movie_ratings_average(
                user_id, movie_ids
            ),
            self.movie_repository.get_movie_stats(movie_ids),
        )

        total_rewatches = max(0, log_stats.total_watches - log_stats.unique_titles)

        summary = StatsSummary(
            total_watches=log_stats.total_watches,
            unique_titles=log_stats.unique_titles,
            total_rewatches=total_rewatches,
            total_minutes=movie_stats.total_runtime,
            vote_average=movie_rating_stats.average_rating
            if movie_rating_stats
            else None,
        )

        distribution = self._build_distribution(log_stats)

        pace = StatsPace(on_track_for=0, current_average=0.0, days_since_last_log=0)

        return StatsResponse(summary=summary, distribution=distribution, pace=pace)

    @staticmethod
    def _build_distribution(log_stats: LogStats) -> StatsDistribution:
        counts = {e.watched_where: e.count for e in log_stats.distribution}
        return StatsDistribution(
            by_method=StatsByMethod(
                cinema=counts.get("cinema", 0),
                streaming=counts.get("streaming", 0),
                home_video=counts.get("homeVideo", 0),
                tv=counts.get("tv", 0),
                other=counts.get("other", 0),
            )
        )
