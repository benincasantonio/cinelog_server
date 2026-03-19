import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.cache_service import CacheService


class TestCacheServiceDisabled:
    """Tests for CacheService when disabled."""

    @pytest_asyncio.fixture
    async def service(self):
        svc = CacheService(enabled=False, url="redis://localhost:6379/0", default_ttl=300)
        yield svc

    @pytest.mark.asyncio
    async def test_get_returns_none(self, service):
        assert await service.get("key") is None

    @pytest.mark.asyncio
    async def test_set_returns_false(self, service):
        assert await service.set("key", {"a": 1}) is False

    @pytest.mark.asyncio
    async def test_delete_returns_false(self, service):
        assert await service.delete("key") is False

    @pytest.mark.asyncio
    async def test_delete_many_returns_zero(self, service):
        assert await service.delete_many(["k1", "k2"]) == 0

    @pytest.mark.asyncio
    async def test_invalidate_pattern_returns_zero(self, service):
        assert await service.invalidate_pattern("cinelog:*") == 0

    @pytest.mark.asyncio
    async def test_health_check_returns_false(self, service):
        assert await service.health_check() is False


class TestCacheServiceEnabled:
    """Tests for CacheService with mocked Redis client."""

    @pytest_asyncio.fixture
    async def service(self):
        with patch("app.services.cache_service.aioredis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_from_url.return_value = mock_client
            svc = CacheService(
                enabled=True, url="redis://localhost:6379/0", default_ttl=300
            )
            svc._mock_client = mock_client  # type: ignore[attr-defined]
            yield svc

    @pytest.mark.asyncio
    async def test_get_returns_data(self, service):
        data = {"title": "Fight Club"}
        service._mock_client.get = AsyncMock(return_value=json.dumps(data))
        result = await service.get("cinelog:movie:550")
        assert result == data
        service._mock_client.get.assert_awaited_once_with("cinelog:movie:550")

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self, service):
        service._mock_client.get = AsyncMock(return_value=None)
        result = await service.get("cinelog:movie:999")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_data(self, service):
        service._mock_client.set = AsyncMock()
        data = {"title": "Fight Club"}
        result = await service.set("cinelog:movie:550", data, ttl=60)
        assert result is True
        service._mock_client.set.assert_awaited_once_with(
            "cinelog:movie:550", json.dumps(data), ex=60
        )

    @pytest.mark.asyncio
    async def test_set_uses_default_ttl(self, service):
        service._mock_client.set = AsyncMock()
        await service.set("key", {"a": 1})
        service._mock_client.set.assert_awaited_once_with(
            "key", json.dumps({"a": 1}), ex=300
        )

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, service):
        service._mock_client.delete = AsyncMock(return_value=1)
        result = await service.delete("cinelog:movie:550")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_missing_key(self, service):
        service._mock_client.delete = AsyncMock(return_value=0)
        result = await service.delete("cinelog:movie:999")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_many(self, service):
        service._mock_client.delete = AsyncMock(return_value=3)
        result = await service.delete_many(["k1", "k2", "k3"])
        assert result == 3
        service._mock_client.delete.assert_awaited_once_with("k1", "k2", "k3")

    @pytest.mark.asyncio
    async def test_delete_many_empty_list(self, service):
        result = await service.delete_many([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, service):
        async def mock_scan_iter(match=None):
            for key in ["cinelog:movie:1", "cinelog:movie:2"]:
                yield key

        service._mock_client.scan_iter = mock_scan_iter
        service._mock_client.delete = AsyncMock(return_value=2)
        result = await service.invalidate_pattern("cinelog:movie:*")
        assert result == 2
        service._mock_client.delete.assert_awaited_once_with(
            "cinelog:movie:1", "cinelog:movie:2"
        )

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matches(self, service):
        async def mock_scan_iter(match=None):
            return
            yield  # noqa: unreachable

        service._mock_client.scan_iter = mock_scan_iter
        result = await service.invalidate_pattern("cinelog:nothing:*")
        assert result == 0

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        service._mock_client.ping = AsyncMock(return_value=True)
        assert await service.health_check() is True

    @pytest.mark.asyncio
    async def test_aclose(self, service):
        service._mock_client.aclose = AsyncMock()
        await service.aclose()
        service._mock_client.aclose.assert_awaited_once()
        assert service._client is None


class TestCacheServiceGracefulDegradation:
    """Tests that Redis errors are caught and don't crash the app."""

    @pytest_asyncio.fixture
    async def service(self):
        with patch("app.services.cache_service.aioredis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_from_url.return_value = mock_client
            svc = CacheService(
                enabled=True, url="redis://localhost:6379/0", default_ttl=300
            )
            svc._mock_client = mock_client  # type: ignore[attr-defined]
            yield svc

    @pytest.mark.asyncio
    async def test_get_handles_connection_error(self, service):
        service._mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        result = await service.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_handles_connection_error(self, service):
        service._mock_client.set = AsyncMock(side_effect=ConnectionError("refused"))
        result = await service.set("key", {"a": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_handles_connection_error(self, service):
        service._mock_client.delete = AsyncMock(side_effect=ConnectionError("refused"))
        result = await service.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_many_handles_connection_error(self, service):
        service._mock_client.delete = AsyncMock(side_effect=ConnectionError("refused"))
        result = await service.delete_many(["k1"])
        assert result == 0

    @pytest.mark.asyncio
    async def test_invalidate_pattern_handles_connection_error(self, service):
        async def failing_scan(match=None):
            raise ConnectionError("refused")
            yield  # noqa: unreachable

        service._mock_client.scan_iter = failing_scan
        result = await service.invalidate_pattern("cinelog:*")
        assert result == 0

    @pytest.mark.asyncio
    async def test_health_check_handles_connection_error(self, service):
        service._mock_client.ping = AsyncMock(side_effect=ConnectionError("refused"))
        assert await service.health_check() is False


class TestCacheServiceSingleton:
    """Tests for singleton lifecycle."""

    def setup_method(self):
        CacheService._singleton = None

    def teardown_method(self):
        CacheService._singleton = None

    def test_initialize_creates_singleton(self):
        config = {"enabled": False, "url": "redis://localhost:6379/0", "default_ttl": 300}
        instance = CacheService.initialize(config)
        assert CacheService.get_instance() is instance

    def test_get_instance_raises_without_initialize(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            CacheService.get_instance()

    @pytest.mark.asyncio
    async def test_aclose_all_clears_singleton(self):
        config = {"enabled": False, "url": "redis://localhost:6379/0", "default_ttl": 300}
        CacheService.initialize(config)
        await CacheService.aclose_all()
        with pytest.raises(RuntimeError):
            CacheService.get_instance()
