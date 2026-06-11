"""PostgreSQL log repository implementation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, distinct, func, select

from app.models.log_model import PostgresLog
from app.repository.repository_base import RepositoryBase
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest
from app.schemas.stats_schemas import LogDistributionEntry, LogStats
from app.utils.datetime_utils import date_end_utc, date_start_utc, to_utc_datetime


class PostgresLogRepository(RepositoryBase):
    """Repository class for PostgreSQL log operations."""

    async def create_log(self, user_id: UUID, create_log_request: LogCreateRequest) -> PostgresLog:
        """Create a new viewing log in PostgreSQL."""

        if create_log_request.movie_id is None:
            raise ValueError("movie_id is required")

        async with self._session_provider() as session:
            log = PostgresLog(
                user_id=user_id,
                movie_id=create_log_request.movie_id,
                tmdb_id=create_log_request.tmdb_id,
                date_watched=to_utc_datetime(create_log_request.date_watched),
                viewing_notes=create_log_request.viewing_notes,
                poster_path=create_log_request.poster_path,
                watched_where=create_log_request.watched_where,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log

    async def find_log_by_id(self, log_id: UUID, user_id: UUID) -> PostgresLog | None:
        """Find an active log by ID owned by the given user."""

        async with self._session_provider() as session:
            statement = select(PostgresLog).where(
                PostgresLog.id == log_id,
                PostgresLog.user_id == user_id,
                PostgresLog.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def update_log(
        self,
        log_id: UUID,
        user_id: UUID,
        update_request: LogUpdateRequest,
    ) -> PostgresLog | None:
        """Update an active log owned by the given user."""

        async with self._session_provider() as session:
            statement = select(PostgresLog).where(
                PostgresLog.id == log_id,
                PostgresLog.user_id == user_id,
                PostgresLog.active(),
            )
            result = await session.execute(statement)
            log = result.scalar_one_or_none()
            if log is None:
                return None

            update_data = update_request.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "date_watched" and value is not None:
                    value = to_utc_datetime(value)
                setattr(log, field, value)

            log.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(log)
            return log

    async def find_logs_by_user_id(
        self,
        user_id: UUID,
        watched_where: str | None = None,
        date_watched_from: date | None = None,
        date_watched_to: date | None = None,
        sort_by: str = "dateWatched",
        sort_order: str = "desc",
    ) -> list[PostgresLog]:
        """Find active logs for a user with optional filters and sorting."""

        async with self._session_provider() as session:
            statement = select(PostgresLog).where(
                PostgresLog.user_id == user_id,
                PostgresLog.active(),
            )

            if watched_where is not None:
                statement = statement.where(PostgresLog.watched_where == watched_where)
            if date_watched_from is not None:
                statement = statement.where(PostgresLog.date_watched >= date_start_utc(date_watched_from))
            if date_watched_to is not None:
                statement = statement.where(PostgresLog.date_watched <= date_end_utc(date_watched_to))

            is_desc = sort_order == "desc"
            order_by: tuple[ColumnElement[Any], ColumnElement[Any]]
            if sort_by == "watchedWhere":
                order_by = (
                    PostgresLog.watched_where.desc() if is_desc else PostgresLog.watched_where.asc(),
                    PostgresLog.created_at.desc() if is_desc else PostgresLog.created_at.asc(),
                )
            else:
                order_by = (
                    PostgresLog.date_watched.desc() if is_desc else PostgresLog.date_watched.asc(),
                    PostgresLog.created_at.desc() if is_desc else PostgresLog.created_at.asc(),
                )

            result = await session.execute(statement.order_by(*order_by))
            return list(result.scalars().all())

    async def find_logs_by_movie_id(
        self,
        movie_id: UUID,
        user_id: UUID | None = None,
    ) -> list[PostgresLog]:
        """Find active logs for a movie, optionally filtered by user."""

        async with self._session_provider() as session:
            statement = select(PostgresLog).where(
                PostgresLog.movie_id == movie_id,
                PostgresLog.active(),
            )
            if user_id is not None:
                statement = statement.where(PostgresLog.user_id == user_id)

            result = await session.execute(statement.order_by(PostgresLog.created_at.asc()))
            return list(result.scalars().all())

    async def delete_log(self, log_id: UUID, user_id: UUID) -> PostgresLog | None:
        """Hard-delete an active log owned by the given user."""

        async with self._session_provider() as session:
            statement = select(PostgresLog).where(
                PostgresLog.id == log_id,
                PostgresLog.user_id == user_id,
                PostgresLog.active(),
            )
            result = await session.execute(statement)
            log = result.scalar_one_or_none()
            if log is None:
                return None

            await session.delete(log)
            await session.commit()
            return log

    async def get_log_stats(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> LogStats:
        """Compute active log statistics for a user."""

        filters = [
            PostgresLog.user_id == user_id,
            PostgresLog.active(),
        ]
        if date_from is not None:
            filters.append(PostgresLog.date_watched >= date_start_utc(date_from))
        if date_to is not None:
            filters.append(PostgresLog.date_watched <= date_end_utc(date_to))

        filtered = (
            select(
                PostgresLog.id,
                PostgresLog.movie_id,
                PostgresLog.watched_where,
            )
            .where(*filters)
            .cte("filtered_logs")
        )

        async with self._session_provider() as session:
            summary_result = await session.execute(
                select(
                    func.count(filtered.c.id),
                    func.count(distinct(filtered.c.movie_id)),
                    func.array_agg(distinct(filtered.c.movie_id)),
                )
            )
            total_watches, unique_titles, unique_movie_ids = summary_result.one()

            if int(total_watches or 0) == 0:
                return LogStats()

            distribution_result = await session.execute(
                select(
                    filtered.c.watched_where,
                    func.count(filtered.c.id),
                )
                .group_by(filtered.c.watched_where)
                .order_by(filtered.c.watched_where.asc())
            )
            distribution = [
                LogDistributionEntry(watched_where=watched_where, count=count)
                for watched_where, count in distribution_result.all()
            ]

            return LogStats(
                total_watches=int(total_watches or 0),
                unique_titles=int(unique_titles or 0),
                unique_movie_ids=list(unique_movie_ids or []),
                distribution=distribution,
            )
