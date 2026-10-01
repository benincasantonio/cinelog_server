import logging

from app.services.cache_service import CacheService
from app.utils.auth_utils import RATE_LIMIT_SESSION_TTL_SECONDS

logger = logging.getLogger(__name__)

RATE_LIMIT_SESSION_CACHE_PREFIX = "rl_session:"
RATE_LIMIT_SESSION_CACHE_VALUE: dict[str, bool] = {"active": True}


class RateLimitCacheService:
    @property
    def _cache(self) -> CacheService:
        return CacheService.get_instance()

    @staticmethod
    def build_session_key(session_id: str) -> str:
        return f"{RATE_LIMIT_SESSION_CACHE_PREFIX}{session_id}"

    async def get_session(self, session_id: str) -> dict[str, bool] | None:
        key = self.build_session_key(session_id)
        data = await self._cache.get(key)
        if data is None:
            logger.debug("Rate-limit session cache miss for key=%s", key)
            return None
        if not isinstance(data, dict):
            logger.warning("Invalid rate-limit session payload for key=%s", key)
            return None

        active = data.get("active")
        if not isinstance(active, bool):
            logger.warning("Invalid rate-limit session payload for key=%s", key)
            return None

        logger.debug("Rate-limit session cache hit for key=%s", key)
        session_data: dict[str, bool] = {"active": active}
        return session_data

    async def upsert_session(self, session_id: str) -> None:
        key = self.build_session_key(session_id)
        await self._cache.set(
            key,
            RATE_LIMIT_SESSION_CACHE_VALUE,
            ttl=RATE_LIMIT_SESSION_TTL_SECONDS,
        )
        logger.debug("Rate-limit session cache set for key=%s", key)
