import logging
import os
from datetime import date
from typing import Any, cast

from beanie import PydanticObjectId

from app.models.log import Log
from app.repository.log_repository import LogRepository
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

LOG_CACHE_TTL = int(os.getenv("LOG_CACHE_TTL", "86400"))


class LogCacheRepository(LogRepository):
    """Redis-backed decorator for raw log repository lookups."""

    @property
    def _cache(self) -> CacheService:
        return CacheService.get_instance()

    @staticmethod
    def build_log_key(log_id: str, user_id: PydanticObjectId) -> str:
        return f"cinelog:logs:id:{user_id}:{log_id}"

    @staticmethod
    def build_user_logs_key(
        user_id: PydanticObjectId,
        watched_where: str | None = None,
        date_watched_from: date | None = None,
        date_watched_to: date | None = None,
        sort_by: str = "dateWatched",
        sort_order: str = "desc",
    ) -> str:
        watched_where_part = watched_where or "all"
        from_part = date_watched_from.isoformat() if date_watched_from is not None else "any"
        to_part = date_watched_to.isoformat() if date_watched_to is not None else "any"
        return (
            f"cinelog:logs:user:{user_id}:where:{watched_where_part}:"
            f"from:{from_part}:to:{to_part}:sort:{sort_by}:{sort_order}"
        )

    @staticmethod
    def build_movie_logs_key(movie_id: str, user_id: PydanticObjectId | None = None) -> str:
        user_part = str(user_id) if user_id is not None else "all"
        return f"cinelog:logs:movie:{movie_id}:user:{user_part}"

    @staticmethod
    def build_user_logs_pattern(user_id: PydanticObjectId) -> str:
        return f"cinelog:logs:user:{user_id}:*"

    @staticmethod
    def build_movie_logs_pattern(movie_id: PydanticObjectId | str) -> str:
        return f"cinelog:logs:movie:{movie_id}:*"

    @staticmethod
    def _serialize_log(log: Log) -> dict[str, Any]:
        return cast(dict[str, Any], log.model_dump(mode="json", by_alias=True))

    @classmethod
    def _serialize_logs(cls, logs: list[Log]) -> list[dict[str, Any]]:
        return [cls._serialize_log(log) for log in logs]

    @staticmethod
    def _deserialize_log(data: dict[str, Any]) -> Log:
        return cast(Log, Log.model_validate(data))

    @classmethod
    def _deserialize_logs(cls, data: list[Any]) -> list[Log]:
        return [cls._deserialize_log(item) for item in data]

    async def _get_log(self, key: str) -> Log | None:
        try:
            data = await self._cache.get(key)
            if data is None:
                logger.debug("Log cache miss for key=%s", key)
                return None
            if not isinstance(data, dict):
                logger.warning("Invalid log cache payload for key=%s", key)
                return None
            logger.debug("Log cache hit for key=%s", key)
            return self._deserialize_log(data)
        except Exception:
            logger.exception("Log cache read failed for key=%s", key)
            return None

    async def _get_logs(self, key: str) -> list[Log] | None:
        try:
            data = await self._cache.get(key)
            if data is None:
                logger.debug("Log cache miss for key=%s", key)
                return None
            if not isinstance(data, list):
                logger.warning("Invalid log list cache payload for key=%s", key)
                return None
            logger.debug("Log cache hit for key=%s", key)
            return self._deserialize_logs(data)
        except Exception:
            logger.exception("Log cache read failed for key=%s", key)
            return None

    async def _set_log(self, key: str, log: Log) -> None:
        try:
            await self._cache.set(key, self._serialize_log(log), ttl=LOG_CACHE_TTL)
            logger.debug("Log cache set for key=%s", key)
        except Exception:
            logger.exception("Log cache write failed for key=%s", key)

    async def _set_logs(self, key: str, logs: list[Log]) -> None:
        try:
            await self._cache.set(key, self._serialize_logs(logs), ttl=LOG_CACHE_TTL)
            logger.debug("Log cache set for key=%s", key)
        except Exception:
            logger.exception("Log cache write failed for key=%s", key)

    async def _delete_key(self, key: str) -> None:
        try:
            await self._cache.delete(key)
            logger.debug("Log cache deleted for key=%s", key)
        except Exception:
            logger.exception("Log cache delete failed for key=%s", key)

    async def _invalidate_pattern(self, pattern: str) -> None:
        try:
            await self._cache.invalidate_pattern(pattern)
            logger.debug("Log cache invalidated for pattern=%s", pattern)
        except Exception:
            logger.exception("Log cache invalidation failed for pattern=%s", pattern)

    async def _invalidate_user_logs(self, user_id: PydanticObjectId) -> None:
        await self._invalidate_pattern(self.build_user_logs_pattern(user_id))

    async def _invalidate_movie_logs(self, movie_id: PydanticObjectId | str) -> None:
        await self._invalidate_pattern(self.build_movie_logs_pattern(movie_id))

    async def _invalidate_log(self, log: Log) -> None:
        await self._delete_key(self.build_log_key(str(log.id), log.user_id))
        await self._invalidate_user_logs(log.user_id)
        await self._invalidate_movie_logs(log.movie_id)

    async def create_log(self, user_id: PydanticObjectId, create_log_request: LogCreateRequest) -> Log:
        log = await super().create_log(user_id, create_log_request)
        await self._invalidate_user_logs(log.user_id)
        await self._invalidate_movie_logs(log.movie_id)
        return log

    async def find_log_by_id(self, log_id: str, user_id: PydanticObjectId) -> Log | None:
        key = self.build_log_key(log_id, user_id)
        cached = await self._get_log(key)
        if cached is not None:
            return cached

        log = await super().find_log_by_id(log_id, user_id)
        if log is not None:
            await self._set_log(key, log)
        return log

    async def update_log(self, log_id: str, user_id: PydanticObjectId, update_request: LogUpdateRequest) -> Log | None:
        log = await super().update_log(log_id, user_id, update_request)
        if log is not None:
            await self._invalidate_log(log)
        return log

    async def find_logs_by_user_id(
        self,
        user_id: PydanticObjectId,
        watched_where: str | None = None,
        date_watched_from: date | None = None,
        date_watched_to: date | None = None,
        sort_by: str = "dateWatched",
        sort_order: str = "desc",
    ) -> list[Log]:
        key = self.build_user_logs_key(
            user_id=user_id,
            watched_where=watched_where,
            date_watched_from=date_watched_from,
            date_watched_to=date_watched_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        cached = await self._get_logs(key)
        if cached is not None:
            return cached

        logs = cast(
            list[Log],
            await super().find_logs_by_user_id(
                user_id=user_id,
                watched_where=watched_where,
                date_watched_from=date_watched_from,
                date_watched_to=date_watched_to,
                sort_by=sort_by,
                sort_order=sort_order,
            ),
        )
        await self._set_logs(key, logs)
        return logs

    async def find_logs_by_movie_id(self, movie_id: str, user_id: PydanticObjectId | None = None) -> list[Log]:
        key = self.build_movie_logs_key(movie_id, user_id)
        cached = await self._get_logs(key)
        if cached is not None:
            return cached

        logs = await super().find_logs_by_movie_id(movie_id, user_id)
        await self._set_logs(key, logs)
        return logs

    async def delete_log(self, log_id: str, user_id: PydanticObjectId) -> bool:
        existing_log = await super().find_log_by_id(log_id, user_id)
        if existing_log is None:
            return False

        deleted = await super()._delete_log(existing_log)
        if deleted:
            await self._invalidate_log(existing_log)
        return deleted
