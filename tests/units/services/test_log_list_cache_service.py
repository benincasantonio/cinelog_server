"""Tests for complete log-list response caching."""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.schemas.log_schemas import LogListRequest, LogListResponse
from app.services.log_list_cache_service import LogListCacheService


@pytest.mark.asyncio
async def test_cache_stores_complete_response_and_invalidates_all_user_filters():
    cache = AsyncMock()
    service = LogListCacheService()
    user_id = uuid4()
    request = LogListRequest(watched_where="cinema", date_watched_from=date(2024, 1, 1), sort_order="asc")
    response = LogListResponse(logs=[], total_watches=0, unique_titles=0, total_rewatches=0)
    cache.get_generation.return_value = 2
    cache.get.return_value = response.model_dump(mode="json")

    with patch("app.services.log_list_cache_service.CacheService.get_instance", return_value=cache):
        assert await service.get(user_id, request) == (response, 2)
        await service.set(user_id, request, response, 2)
        await service.invalidate_user(user_id)

    key = service.build_key(user_id, request, 2)
    cache.get_generation.assert_awaited_once_with("log-list", str(user_id))
    cache.get.assert_awaited_once_with(key)
    cache.set.assert_awaited_once_with(key, response.model_dump(mode="json"))
    cache.bump_generation.assert_awaited_once_with("log-list", str(user_id))
    assert key != service.build_key(user_id, LogListRequest(), 2)
    assert key != service.build_key(uuid4(), request, 2)
    assert key != service.build_key(user_id, request, 3)


@pytest.mark.asyncio
async def test_inflight_cache_fill_cannot_restore_invalidated_response():
    cache = AsyncMock()
    service = LogListCacheService()
    user_id = uuid4()
    request = LogListRequest()
    old_response = LogListResponse(logs=[], total_watches=0, unique_titles=0, total_rewatches=0)
    values = {}
    generation = 0

    async def read_generation(_context, _user_id):
        return generation

    async def bump_generation(_context, _user_id):
        nonlocal generation
        generation += 1
        return generation

    async def read(key):
        return values.get(key)

    async def write(key, value):
        values[key] = value

    cache.get_generation.side_effect = read_generation
    cache.bump_generation.side_effect = bump_generation
    cache.get.side_effect = read
    cache.set.side_effect = write

    with patch("app.services.log_list_cache_service.CacheService.get_instance", return_value=cache):
        missing, old_generation = await service.get(user_id, request)
        assert missing is None
        await service.invalidate_user(user_id)
        await service.set(user_id, request, old_response, old_generation)
        current, new_generation = await service.get(user_id, request)

    assert current is None
    assert new_generation == 1
    assert service.build_key(user_id, request, 0) in values
    assert service.build_key(user_id, request, 1) not in values


@pytest.mark.asyncio
async def test_cache_errors_fall_back_to_database_and_do_not_block_writes():
    cache = AsyncMock()
    cache.get_generation.side_effect = RuntimeError("Redis unavailable")
    cache.set.side_effect = RuntimeError("Redis unavailable")
    cache.bump_generation.side_effect = RuntimeError("Redis unavailable")
    service = LogListCacheService()
    user_id = uuid4()
    request = LogListRequest()
    response = LogListResponse(logs=[], total_watches=0, unique_titles=0, total_rewatches=0)

    with patch("app.services.log_list_cache_service.CacheService.get_instance", return_value=cache):
        assert await service.get(user_id, request) == (None, None)
        await service.set(user_id, request, response, None)
        cache.set.assert_not_awaited()
        await service.set(user_id, request, response, 0)
        await service.invalidate_user(user_id)
