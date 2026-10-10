from datetime import UTC, datetime
from json import JSONDecodeError
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.infrastructure.redis import RedisClient
from app.providers.tmdb.cache import TMDB_DETAILS_CACHE_TTL, TMDB_SEARCH_CACHE_TTL, TMDBCache
from app.providers.tmdb.schemas import TMDBDetailsSnapshot, TMDBSearchSnapshot

OBSERVED_AT = datetime(2024, 1, 1, 10, tzinfo=UTC)


async def test_search_roundtrip_retains_timestamp_and_normalizes_query(search_data):
    redis = AsyncMock(spec=RedisClient)
    snapshot = TMDBSearchSnapshot(payload=search_data, observed_at=OBSERVED_AT)
    cache = TMDBCache(redis)
    await cache.set_search("  FIGHT Club  ", "it-IT", snapshot)
    redis.set.assert_awaited_once_with(
        "cinelog:tmdb:search:v2:it-IT:fight club", snapshot.model_dump(mode="json"), ttl=TMDB_SEARCH_CACHE_TTL
    )
    redis.get.return_value = redis.set.await_args.args[1]
    assert await cache.get_search("Fight Club", "it-IT") == snapshot
    redis.get.return_value = None
    assert await cache.get_search("Fight Club", "fr-FR") is None
    assert redis.get.await_args.args[0] == "cinelog:tmdb:search:v2:fr-FR:fight club"


async def test_details_roundtrip_uses_captured_generation(details_data):
    redis = AsyncMock(spec=RedisClient)
    redis.hget.return_value = "3"
    redis.get.return_value = None
    cache = TMDBCache(redis)
    snapshot = TMDBDetailsSnapshot(payload=details_data, observed_at=OBSERVED_AT)
    assert await cache.get_details("550", "fr-FR") == (None, 3)
    redis.hget.assert_awaited_once_with("cinelog:cache-generation:tmdb-details:v2:550:fr-FR", "value")
    redis.hincrby.return_value = 4
    assert await cache.invalidate_details("550", "fr-FR") == 4
    redis.hincrby.assert_awaited_once_with("cinelog:cache-generation:tmdb-details:v2:550:fr-FR", "value")
    await cache.set_details("550", "fr-FR", snapshot, generation=3)
    redis.set.assert_awaited_once_with(
        "cinelog:tmdb:details:v2:fr-FR:550:generation:3",
        snapshot.model_dump(mode="json"),
        ttl=TMDB_DETAILS_CACHE_TTL,
    )
    redis.hget.assert_awaited_once()
    redis.get.return_value = redis.set.await_args.args[1]
    assert await cache.get_details("550", "fr-FR") == (snapshot, 3)
    assert cache.details_key("550", "it-IT", 3) != cache.details_key("550", "fr-FR", 3)


async def test_default_cache_resolves_shared_client_lazily(monkeypatch):
    cache = TMDBCache()
    redis = AsyncMock(spec=RedisClient)
    redis.get.return_value = None
    monkeypatch.setattr(RedisClient, "get_instance", lambda: redis)
    assert await cache.get_search("film", "en-US") is None


@pytest.mark.parametrize("operation", ["get_search", "get_details"])
@pytest.mark.parametrize("corruption", ["json", "legacy", "envelope", "payload", "timestamp"])
async def test_unreadable_snapshot_is_a_miss(operation, corruption, search_data, details_data):
    redis = AsyncMock(spec=RedisClient)
    redis.hget.return_value = "3"
    payload = search_data if operation == "get_search" else details_data
    if corruption == "json":
        redis.get.side_effect = JSONDecodeError("Invalid JSON", "{", 1)
    elif corruption == "legacy":
        redis.get.return_value = payload
    elif corruption == "envelope":
        redis.get.return_value = []
    elif corruption == "payload":
        redis.get.return_value = {"payload": {}, "observed_at": OBSERVED_AT.isoformat()}
    else:
        redis.get.return_value = {"payload": payload, "observed_at": "invalid"}

    result = await getattr(TMDBCache(redis), operation)("550", "it-IT")

    assert result == (None if operation == "get_search" else (None, 3))
    if operation == "get_details":
        redis.hget.assert_awaited_once_with("cinelog:cache-generation:tmdb-details:v2:550:it-IT", "value")
        redis.get.assert_awaited_once_with("cinelog:tmdb:details:v2:it-IT:550:generation:3")
    redis.hincrby.assert_not_awaited()
    redis.delete.assert_not_awaited()


@pytest.mark.parametrize("operation", ["get_search", "get_details"])
@pytest.mark.parametrize("error", [RedisConnectionError, RedisTimeoutError, ValueError])
async def test_cache_does_not_hide_unrelated_errors(operation, error):
    redis = AsyncMock(spec=RedisClient)
    redis.hget.return_value = "3"
    redis.get.side_effect = error("unavailable")
    with pytest.raises(error, match="unavailable"):
        await getattr(TMDBCache(redis), operation)("550", "it-IT")


async def test_invalid_generation_does_not_become_a_cache_miss():
    redis = AsyncMock(spec=RedisClient)
    redis.hget.return_value = "invalid"
    with pytest.raises(ValueError):
        await TMDBCache(redis).get_details("550", "it-IT")
    redis.get.assert_not_awaited()
