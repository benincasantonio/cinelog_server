from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rate_limit_cache_service import (
    RATE_LIMIT_SESSION_CACHE_VALUE,
    RateLimitCacheService,
)
from app.utils.auth_utils import RATE_LIMIT_SESSION_TTL_SECONDS


class TestBuildSessionKey:
    def test_build_session_key(self):
        assert (
            RateLimitCacheService.build_session_key("session123")
            == "rl_session:session123"
        )


class TestGetSession:
    @pytest.mark.asyncio
    async def test_returns_none_on_cache_miss(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)

        with patch(
            "app.services.rate_limit_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = RateLimitCacheService()
            result = await service.get_session("missing-session")
            assert result is None
            mock_cache.get.assert_awaited_once_with("rl_session:missing-session")

    @pytest.mark.asyncio
    async def test_returns_session_data_on_cache_hit(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=RATE_LIMIT_SESSION_CACHE_VALUE)

        with patch(
            "app.services.rate_limit_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = RateLimitCacheService()
            result = await service.get_session("known-session")
            assert result == RATE_LIMIT_SESSION_CACHE_VALUE
            mock_cache.get.assert_awaited_once_with("rl_session:known-session")


class TestUpsertSession:
    @pytest.mark.asyncio
    async def test_stores_session_with_expected_ttl(self):
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)

        with patch(
            "app.services.rate_limit_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = RateLimitCacheService()
            await service.upsert_session("session123")

            mock_cache.set.assert_awaited_once_with(
                "rl_session:session123",
                RATE_LIMIT_SESSION_CACHE_VALUE,
                ttl=RATE_LIMIT_SESSION_TTL_SECONDS,
            )
