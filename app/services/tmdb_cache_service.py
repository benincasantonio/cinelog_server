import logging
import os

from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

TMDB_SEARCH_CACHE_TTL = int(os.getenv("TMDB_SEARCH_CACHE_TTL", "600"))
TMDB_DETAILS_CACHE_TTL = int(os.getenv("TMDB_DETAILS_CACHE_TTL", "86400"))


class TMDBCacheService:
    def __init__(self) -> None:
        self._cache_instance: CacheService | None = None
        self._cache_resolved = False

    @property
    def _cache(self) -> CacheService | None:
        if not self._cache_resolved:
            try:
                self._cache_instance = CacheService.get_instance()
            except RuntimeError:
                self._cache_instance = None
            self._cache_resolved = True
        return self._cache_instance

    @staticmethod
    def build_search_key(query: str) -> str:
        normalized = query.strip().lower()
        return f"cinelog:tmdb:search:{normalized}"

    @staticmethod
    def build_details_key(tmdb_id: int) -> str:
        return f"cinelog:tmdb:details:{tmdb_id}"

    async def get_search(self, query: str) -> TMDBMovieSearchResult | None:
        if self._cache is None:
            return None
        key = self.build_search_key(query)
        data = await self._cache.get(key)
        if data is None:
            logger.debug("TMDB cache miss for key=%s", key)
            return None
        logger.debug("TMDB cache hit for key=%s", key)
        return TMDBMovieSearchResult.model_validate(data)

    async def set_search(self, query: str, result: TMDBMovieSearchResult) -> None:
        if self._cache is None:
            return
        key = self.build_search_key(query)
        await self._cache.set(
            key, result.model_dump(mode="json"), ttl=TMDB_SEARCH_CACHE_TTL
        )
        logger.debug("TMDB cache set for key=%s", key)

    async def get_details(self, tmdb_id: int) -> TMDBMovieDetails | None:
        if self._cache is None:
            return None
        key = self.build_details_key(tmdb_id)
        data = await self._cache.get(key)
        if data is None:
            logger.debug("TMDB cache miss for key=%s", key)
            return None
        logger.debug("TMDB cache hit for key=%s", key)
        return TMDBMovieDetails.model_validate(data)

    async def set_details(self, tmdb_id: int, details: TMDBMovieDetails) -> None:
        if self._cache is None:
            return
        key = self.build_details_key(tmdb_id)
        await self._cache.set(
            key, details.model_dump(mode="json"), ttl=TMDB_DETAILS_CACHE_TTL
        )
        logger.debug("TMDB cache set for key=%s", key)
