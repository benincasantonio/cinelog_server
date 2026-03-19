import logging
import os

from beanie import PydanticObjectId

from app.schemas.stats_schemas import StatsResponse
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

STATS_CACHE_TTL = int(os.getenv("STATS_CACHE_TTL", "864000"))


class StatsCacheService:
    def __init__(self):
        try:
            self._cache = CacheService.get_instance()
        except RuntimeError:
            self._cache = None

    @staticmethod
    def build_key(
        user_id: PydanticObjectId,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> str:
        if year_from is None and year_to is None:
            return f"cinelog:stats:{user_id}:all"
        from_part = str(year_from) if year_from is not None else "*"
        to_part = str(year_to) if year_to is not None else "*"
        return f"cinelog:stats:{user_id}:{from_part}:{to_part}"

    async def get_stats(
        self,
        user_id: PydanticObjectId,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> StatsResponse | None:
        if self._cache is None:
            return None

        key = self.build_key(user_id, year_from, year_to)
        data = await self._cache.get(key)
        if data is None:
            logger.debug("Cache miss for key=%s", key)
            return None
        logger.info("Cache hit for key=%s", key)
        return StatsResponse.model_validate(data)

    async def set_stats(
        self,
        user_id: PydanticObjectId,
        year_from: int | None = None,
        year_to: int | None = None,
        stats: StatsResponse | None = None,
    ) -> None:
        if stats is None:
            return
        if self._cache is None:
            return

        key = self.build_key(user_id, year_from, year_to)
        await self._cache.set(key, stats.model_dump(mode="json"), ttl=STATS_CACHE_TTL)
        logger.debug("Cache set for key=%s", key)

    async def invalidate_user_stats(self, user_id: PydanticObjectId) -> None:
        if self._cache is None:
            return

        await self._cache.invalidate_pattern(f"cinelog:stats:{user_id}:*")
        logger.info("Cache invalidated for user_id=%s", user_id)
