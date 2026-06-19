"""PostgreSQL read repository for user viewing statistics."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import distinct, func, select

from app.models.log_model import Log
from app.models.movie_model import Movie
from app.models.movie_rating_model import MovieRating
from app.repository.repository_base import RepositoryBase
from app.schemas.stats_schemas import StatsByMethod, UserStatsAggregate
from app.utils.datetime_utils import date_end_utc, date_start_utc


class StatsRepository(RepositoryBase):
    """Compute the stats read model across logs, movies, and ratings."""

    async def get_user_stats(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> UserStatsAggregate:
        """Compute user statistics with one PostgreSQL statement."""

        filters = [
            Log.user_id == user_id,
            Log.active(),
        ]
        if date_from is not None:
            filters.append(Log.date_watched >= date_start_utc(date_from))
        if date_to is not None:
            filters.append(Log.date_watched <= date_end_utc(date_to))

        filtered_logs = (
            select(
                Log.id,
                Log.movie_id,
                Log.watched_where,
            )
            .where(*filters)
            .cte("filtered_logs")
        )
        watched_movie_ids = select(filtered_logs.c.movie_id).distinct()

        average_rating = (
            select(func.avg(MovieRating.rating))
            .where(
                MovieRating.user_id == user_id,
                MovieRating.movie_id.in_(watched_movie_ids),
                MovieRating.active(),
                MovieRating.rating.is_not(None),
            )
            .scalar_subquery()
        )

        statement = (
            select(
                func.count(filtered_logs.c.id).label("total_watches"),
                func.count(distinct(filtered_logs.c.movie_id)).label("unique_titles"),
                func.coalesce(func.sum(Movie.runtime), 0).label("total_minutes"),
                average_rating.label("vote_average"),
                func.count(filtered_logs.c.id).filter(filtered_logs.c.watched_where == "cinema").label("cinema"),
                func.count(filtered_logs.c.id).filter(filtered_logs.c.watched_where == "streaming").label("streaming"),
                func.count(filtered_logs.c.id).filter(filtered_logs.c.watched_where == "homeVideo").label("home_video"),
                func.count(filtered_logs.c.id).filter(filtered_logs.c.watched_where == "tv").label("tv"),
                func.count(filtered_logs.c.id).filter(filtered_logs.c.watched_where == "other").label("other"),
            )
            .select_from(filtered_logs)
            .outerjoin(
                Movie,
                (Movie.id == filtered_logs.c.movie_id) & Movie.active(),
            )
        )

        async with self._session_provider() as session:
            values = (await session.execute(statement)).mappings().one()

        return UserStatsAggregate(
            **values,
            by_method=StatsByMethod.model_validate(values),
        )
