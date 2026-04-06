import asyncio
import json
import logging
from threading import Lock
from typing import Any

import redis.asyncio as aioredis

from app.config.redis import RedisConfig

logger = logging.getLogger(__name__)

CacheValue = dict[str, Any] | list[Any]


class CacheService:
    _singleton: "CacheService | None" = None
    _singleton_lock = Lock()

    def __init__(self, url: str, default_ttl: int):
        self._default_ttl = default_ttl
        self._client: aioredis.Redis = aioredis.from_url(url, decode_responses=True)

    @classmethod
    def initialize(cls, config: RedisConfig) -> "CacheService":
        with cls._singleton_lock:
            cls._singleton = cls(
                url=config["url"],
                default_ttl=config["default_ttl"],
            )
            return cls._singleton

    @classmethod
    def get_instance(cls) -> "CacheService":
        with cls._singleton_lock:
            if cls._singleton is None:
                raise RuntimeError(
                    "CacheService not initialized. Call initialize() first."
                )
            return cls._singleton

    async def get(self, key: str) -> CacheValue | None:
        data = await self._client.get(key)
        if data is None:
            return None
        result: CacheValue = json.loads(data)
        return result

    async def set(self, key: str, value: CacheValue, ttl: int | None = None) -> bool:
        serialized = json.dumps(value)
        await self._client.set(key, serialized, ex=ttl or self._default_ttl)
        return True

    async def delete(self, key: str) -> bool:
        result = int(await self._client.delete(key))
        return result > 0

    async def delete_many(self, keys: list[str]) -> int:
        if not keys:
            return 0
        return int(await self._client.delete(*keys))

    async def invalidate_pattern(self, pattern: str) -> int:
        keys: list[str] = []
        async for key in self._client.scan_iter(match=pattern):
            keys.append(key)
        if not keys:
            return 0
        return int(await self._client.delete(*keys))

    async def health_check(self) -> bool:
        try:
            result = self._client.ping()
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception:
            logger.exception("Cache health check failed")
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
        with CacheService._singleton_lock:
            if CacheService._singleton is self:
                CacheService._singleton = None

    @classmethod
    async def aclose_all(cls) -> None:
        with cls._singleton_lock:
            singleton = cls._singleton
            cls._singleton = None
        if singleton is not None:
            await singleton.aclose()
