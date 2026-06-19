from collections.abc import Sequence
from datetime import date
from typing import Protocol, TypeVar

from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest

IdType = TypeVar("IdType", contravariant=True)
LogType = TypeVar("LogType", covariant=True)


class LogRepositoryProtocol(Protocol[IdType, LogType]):
    """Protocol for log repository implementations."""

    async def create_log(self, user_id: IdType, create_log_request: LogCreateRequest) -> LogType:
        """Create a new viewing log."""

    async def find_log_by_id(self, log_id: IdType, user_id: IdType) -> LogType | None:
        """Find a log entry by ID, scoped to the owning user."""

    async def update_log(
        self,
        log_id: IdType,
        user_id: IdType,
        update_request: LogUpdateRequest,
    ) -> LogType | None:
        """Update a log entry by ID, scoped to the owning user."""

    async def find_logs_by_user_id(
        self,
        user_id: IdType,
        watched_where: str | None = None,
        date_watched_from: date | None = None,
        date_watched_to: date | None = None,
        sort_by: str = "dateWatched",
        sort_order: str = "desc",
    ) -> Sequence[LogType]:
        """Find logs for a specific user with optional filtering and sorting."""

    async def find_logs_by_movie_id(
        self,
        movie_id: IdType,
        user_id: IdType | None = None,
    ) -> Sequence[LogType]:
        """Find logs for a movie, optionally filtered by user."""

    async def delete_log(self, log_id: IdType, user_id: IdType) -> LogType | None:
        """Delete a log entry by ID, scoped to the owning user."""
