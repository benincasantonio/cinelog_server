"""Cache complete log-list responses for a short period."""

import logging
from uuid import UUID

from app.schemas.log_schemas import LogListRequest, LogListResponse
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)
LOG_LIST_CONTEXT = "log-list"


class LogListCacheService:
    @staticmethod
    def build_key(user_id: UUID, request: LogListRequest, generation: int) -> str:
        watched_where = request.watched_where or "all"
        date_from = request.date_watched_from.isoformat() if request.date_watched_from else "any"
        date_to = request.date_watched_to.isoformat() if request.date_watched_to else "any"
        return (
            f"cinelog:log-list-response:v1:{user_id}:generation:{generation}:where:{watched_where}:"
            f"from:{date_from}:to:{date_to}:sort:{request.sort_by}:{request.sort_order}"
        )

    async def get(self, user_id: UUID, request: LogListRequest) -> tuple[LogListResponse | None, int | None]:
        try:
            cache = CacheService.get_instance()
            generation = await cache.get_generation(LOG_LIST_CONTEXT, str(user_id))
            data = await cache.get(self.build_key(user_id, request, generation))
            return (LogListResponse.model_validate(data) if isinstance(data, dict) else None, generation)
        except Exception:
            logger.exception("Log list cache read failed for user_id=%s", user_id)
            return None, None

    async def set(
        self, user_id: UUID, request: LogListRequest, response: LogListResponse, generation: int | None
    ) -> None:
        if generation is None:
            return
        try:
            await CacheService.get_instance().set(
                self.build_key(user_id, request, generation), response.model_dump(mode="json")
            )
        except Exception:
            logger.exception("Log list cache write failed for user_id=%s", user_id)

    async def invalidate_user(self, user_id: UUID) -> None:
        try:
            await CacheService.get_instance().bump_generation(LOG_LIST_CONTEXT, str(user_id))
        except Exception:
            logger.exception("Log list cache invalidation failed for user_id=%s", user_id)
