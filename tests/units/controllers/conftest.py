from unittest.mock import patch

import pytest

from app.services.cache_service import CacheService
from app.services.rate_limit_cache_service import RateLimitCacheService


class FakeRedisClient:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        return True

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_cache_client() -> FakeRedisClient:
    return FakeRedisClient()


@pytest.fixture(autouse=True)
def initialize_controller_cache_service(fake_cache_client: FakeRedisClient):
    CacheService._singleton = None
    with patch(
        "app.services.cache_service.aioredis.from_url",
        return_value=fake_cache_client,
    ):
        CacheService.initialize(
            {
                "url": "redis://localhost:6379/0",
                "default_ttl": 300,
            }
        )
        yield
    CacheService._singleton = None


@pytest.fixture
def rate_limit_cache_service() -> RateLimitCacheService:
    return RateLimitCacheService()
