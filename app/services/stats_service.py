from datetime import date

from app.schemas.movie_rating_schemas import MovieRatingStats
from beanie import PydanticObjectId

from app.models.log import Log
from app.models.movie import Movie
from app.schemas.movie_schemas import MovieStats
from app.repository.log_repository import LogRepository
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.schemas.stats_schemas import (
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
        """
        Retrieve summary stats for a given user.

        Returns a dictionary matching the `StatsResponse` schema. For now this
        implements only the `summary` section; `distribution` and `pace` are
        returned with zeroed/default values.
        """
        date_from: date | None = (
            date(year_from, 1, 1) if year_from is not None else None
        )
        date_to: date | None = date(year_to, 12, 31) if year_to is not None else None

        logs = await self.log_repository.find_logs_by_user_id(
            user_id,
            sort_by="dateWatched",
            sort_order="desc",
            watched_where=None,
            date_watched_from=date_from,
            date_watched_to=date_to,
        )

        movie_ids: set[PydanticObjectId] = {log.movie_id for log in logs}

        movie_rating_stats = (
            await self.movie_rating_repository.get_user_movie_ratings_avarage(
                user_id, movie_ids
            )
        )

        movie_stats = await self.movie_repository.get_movie_stats(movie_ids)

        summary = self._compute_summary(logs, movie_rating_stats, movie_stats)

        distribution = self._compute_distribution(logs)

        pace: StatsPace = StatsPace(
            on_track_for=0, current_average=0.0, days_since_last_log=0
        )

        return StatsResponse(summary=summary, distribution=distribution, pace=pace)

    def _compute_summary(
        self,
        logs: list[Log],
        movie_rating_stats: MovieRatingStats,
        movie_stats: MovieStats,
    ) -> StatsSummary:
        """
        Compute summary stats from a list of log records.

        Args:
            logs: list of Log objects returned by the repository

        Returns:
            dict with keys: total_watches, unique_titles, total_rewatches, total_minutes
        """
        if not logs:
            return StatsSummary(
                total_watches=0,
                unique_titles=0,
                total_rewatches=0,
                total_minutes=0,
                vote_average=None,
            )

        total_watches = len(logs)

        # unique titles are unique movieId values
        unique_titles = len({str(log.movie_id) for log in logs}) if logs else 0

        total_rewatches = max(0, total_watches - unique_titles)

        return StatsSummary(
            total_watches=total_watches,
            unique_titles=unique_titles,
            total_rewatches=total_rewatches,
            total_minutes=movie_stats.total_runtime,
            vote_average=movie_rating_stats.average_rating
            if movie_rating_stats
            else None,
        )

    def _compute_distribution(self, logs: list) -> StatsDistribution:
        """
        Compute the distribution stats from a list of log records.

        Args:
            logs: list of Log objects returned by the repository

        Returns:
            StatsDistribution object with counts of watches by method (cinema, streaming, home video, tv, other)

        """

        distribution: StatsDistribution = StatsDistribution(
            by_method=StatsByMethod(
                cinema=0,
                streaming=0,
                home_video=0,
                tv=0,
                other=0,
            )
        )

        for log in logs:
            watched_where = getattr(log, "watched_where", None)

            if watched_where == "cinema":
                distribution.by_method.cinema += 1
            elif watched_where == "streaming":
                distribution.by_method.streaming += 1
            elif watched_where == "homeVideo":
                distribution.by_method.home_video += 1
            elif watched_where == "tv":
                distribution.by_method.tv += 1
            elif watched_where == "other":
                distribution.by_method.other += 1

        return distribution
