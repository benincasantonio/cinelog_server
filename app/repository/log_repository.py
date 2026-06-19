"""PostgreSQL log repository implementation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, select

from app.models.log_model import Log
from app.repository.repository_base import RepositoryBase
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest
from app.utils.datetime_utils import date_end_utc, date_start_utc, to_utc_datetime


class LogRepository(RepositoryBase):
    """Repository class for PostgreSQL log operations."""

    async def create_log(self, user_id: UUID, create_log_request: LogCreateRequest) -> Log:
        """Create a new viewing log in PostgreSQL."""

        if create_log_request.movie_id is None:
            raise ValueError("movie_id is required")

        async with self._session_provider() as session:
            log = Log(
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

    async def find_log_by_id(self, log_id: UUID, user_id: UUID) -> Log | None:
        """Find an active log by ID owned by the given user."""

        async with self._session_provider() as session:
            statement = select(Log).where(
                Log.id == log_id,
                Log.user_id == user_id,
                Log.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def update_log(
        self,
        log_id: UUID,
        user_id: UUID,
        update_request: LogUpdateRequest,
    ) -> Log | None:
        """Update an active log owned by the given user."""

        async with self._session_provider() as session:
            statement = select(Log).where(
                Log.id == log_id,
                Log.user_id == user_id,
                Log.active(),
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
    ) -> list[Log]:
        """Find active logs for a user with optional filters and sorting."""

        async with self._session_provider() as session:
            statement = select(Log).where(
                Log.user_id == user_id,
                Log.active(),
            )

            if watched_where is not None:
                statement = statement.where(Log.watched_where == watched_where)
            if date_watched_from is not None:
                statement = statement.where(Log.date_watched >= date_start_utc(date_watched_from))
            if date_watched_to is not None:
                statement = statement.where(Log.date_watched <= date_end_utc(date_watched_to))

            is_desc = sort_order == "desc"
            order_by: tuple[ColumnElement[Any], ColumnElement[Any]]
            if sort_by == "watchedWhere":
                order_by = (
                    Log.watched_where.desc() if is_desc else Log.watched_where.asc(),
                    Log.created_at.desc() if is_desc else Log.created_at.asc(),
                )
            else:
                order_by = (
                    Log.date_watched.desc() if is_desc else Log.date_watched.asc(),
                    Log.created_at.desc() if is_desc else Log.created_at.asc(),
                )

            result = await session.execute(statement.order_by(*order_by))
            return list(result.scalars().all())

    async def find_logs_by_movie_id(
        self,
        movie_id: UUID,
        user_id: UUID | None = None,
    ) -> list[Log]:
        """Find active logs for a movie, optionally filtered by user."""

        async with self._session_provider() as session:
            statement = select(Log).where(
                Log.movie_id == movie_id,
                Log.active(),
            )
            if user_id is not None:
                statement = statement.where(Log.user_id == user_id)

            result = await session.execute(statement.order_by(Log.created_at.asc()))
            return list(result.scalars().all())

    async def delete_log(self, log_id: UUID, user_id: UUID) -> Log | None:
        """Hard-delete an active log owned by the given user."""

        async with self._session_provider() as session:
            statement = select(Log).where(
                Log.id == log_id,
                Log.user_id == user_id,
                Log.active(),
            )
            result = await session.execute(statement)
            log = result.scalar_one_or_none()
            if log is None:
                return None

            await session.delete(log)
            await session.commit()
            return log
