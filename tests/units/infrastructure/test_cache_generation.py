from unittest.mock import AsyncMock

import pytest

from app.infrastructure.cache_generation import bump_generation, generation_key, get_generation
from app.infrastructure.redis import RedisClient


def test_generation_keys_preserve_namespace_and_isolate_context_and_scope():
    key = generation_key("log-list", "user-1")
    assert key == "cinelog:cache-generation:log-list:user-1"
    assert key != generation_key("stats", "user-1")
    assert key != generation_key("log-list", "user-2")
    assert generation_key("tmdb-details:v2", "550:it-IT") == "cinelog:cache-generation:tmdb-details:v2:550:it-IT"


@pytest.mark.parametrize(("stored", "expected"), [(None, 0), ("0", 0), ("2", 2)])
async def test_get_generation_reads_existing_counter_or_defaults_to_zero(stored, expected):
    client = AsyncMock(spec=RedisClient)
    client.hget.return_value = stored
    assert await get_generation(client, "log-list", "user-1") == expected
    client.hget.assert_awaited_once_with("cinelog:cache-generation:log-list:user-1", "value")
    client.hincrby.assert_not_awaited()


async def test_bump_generation_uses_atomic_increment_without_reading():
    client = AsyncMock(spec=RedisClient)
    client.hincrby.return_value = 3
    assert await bump_generation(client, "log-list", "user-1") == 3
    client.hincrby.assert_awaited_once_with("cinelog:cache-generation:log-list:user-1", "value")
    client.hget.assert_not_awaited()


@pytest.mark.parametrize(("operation", "method"), [(get_generation, "hget"), (bump_generation, "hincrby")])
async def test_redis_errors_propagate_to_caller(operation, method):
    client = AsyncMock(spec=RedisClient)
    getattr(client, method).side_effect = ConnectionError("refused")
    with pytest.raises(ConnectionError, match="refused"):
        await operation(client, "log-list", "user-1")


async def test_invalid_counter_is_not_silently_reset():
    client = AsyncMock(spec=RedisClient)
    client.hget.return_value = "invalid"
    with pytest.raises(ValueError):
        await get_generation(client, "log-list", "user-1")
