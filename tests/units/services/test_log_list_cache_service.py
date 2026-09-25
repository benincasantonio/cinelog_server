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
    cache.get.return_value = response.model_dump(mode="json")

    with patch("app.services.log_list_cache_service.CacheService.get_instance", return_value=cache):
        assert await service.get(user_id, request) == response
        await service.set(user_id, request, response)
        await service.invalidate_user(user_id)

    key = service.build_key(user_id, request)
    cache.get.assert_awaited_once_with(key)
    cache.set.assert_awaited_once_with(key, response.model_dump(mode="json"))
    cache.invalidate_pattern.assert_awaited_once_with(f"cinelog:log-list-response:v1:{user_id}:*")
    assert key != service.build_key(user_id, LogListRequest())
    assert key != service.build_key(uuid4(), request)


@pytest.mark.asyncio
async def test_cache_errors_fall_back_to_database_and_do_not_block_writes():
    cache = AsyncMock()
    cache.get.side_effect = RuntimeError("Redis unavailable")
    cache.set.side_effect = RuntimeError("Redis unavailable")
    cache.invalidate_pattern.side_effect = RuntimeError("Redis unavailable")
    service = LogListCacheService()
    user_id = uuid4()
    request = LogListRequest()
    response = LogListResponse(logs=[], total_watches=0, unique_titles=0, total_rewatches=0)

    with patch("app.services.log_list_cache_service.CacheService.get_instance", return_value=cache):
        assert await service.get(user_id, request) is None
        await service.set(user_id, request, response)
        await service.invalidate_user(user_id)
