"""Private TMDB cache: source DTOs, original observation time and generations."""

import os
from json import JSONDecodeError

from pydantic import ValidationError

from app.infrastructure.cache_generation import bump_generation, get_generation
from app.infrastructure.redis import RedisClient
from app.providers.tmdb.schemas import TMDBDetailsSnapshot, TMDBSearchSnapshot

TMDB_SEARCH_CACHE_TTL = int(os.getenv("TMDB_SEARCH_CACHE_TTL", "600"))
TMDB_DETAILS_CACHE_TTL = int(os.getenv("TMDB_DETAILS_CACHE_TTL", "86400"))
TMDB_DETAILS_CONTEXT = "tmdb-details:v2"


class TMDBCache:
    def __init__(self, redis: RedisClient | None = None):
        self._redis = redis

    @property
    def _client(self) -> RedisClient:
        # Provider construction may precede application startup.
        return self._redis if self._redis is not None else RedisClient.get_instance()

    @staticmethod
    def search_key(query: str, locale: str) -> str:
        return f"cinelog:tmdb:search:v2:{locale}:{query.strip().lower()}"

    @staticmethod
    def details_key(external_id: str, locale: str, generation: int) -> str:
        return f"cinelog:tmdb:details:v2:{locale}:{external_id}:generation:{generation}"

    async def get_search(self, query: str, locale: str) -> TMDBSearchSnapshot | None:
        try:
            data = await self._client.get(self.search_key(query, locale))
            return TMDBSearchSnapshot.model_validate(data) if data is not None else None
        except (JSONDecodeError, ValidationError):
            return None

    async def set_search(self, query: str, locale: str, snapshot: TMDBSearchSnapshot) -> None:
        await self._client.set(
            self.search_key(query, locale), snapshot.model_dump(mode="json"), ttl=TMDB_SEARCH_CACHE_TTL
        )

    async def get_details(self, external_id: str, locale: str) -> tuple[TMDBDetailsSnapshot | None, int]:
        generation = await get_generation(self._client, TMDB_DETAILS_CONTEXT, f"{external_id}:{locale}")
        try:
            data = await self._client.get(self.details_key(external_id, locale, generation))
            snapshot = TMDBDetailsSnapshot.model_validate(data) if data is not None else None
        except (JSONDecodeError, ValidationError):
            snapshot = None
        return snapshot, generation

    async def set_details(self, external_id: str, locale: str, snapshot: TMDBDetailsSnapshot, generation: int) -> None:
        await self._client.set(
            self.details_key(external_id, locale, generation),
            snapshot.model_dump(mode="json"),
            ttl=TMDB_DETAILS_CACHE_TTL,
        )

    async def invalidate_details(self, external_id: str, locale: str) -> int:
        return await bump_generation(self._client, TMDB_DETAILS_CONTEXT, f"{external_id}:{locale}")
