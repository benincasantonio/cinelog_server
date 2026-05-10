from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from beanie import PydanticObjectId

from app.models.log import Log
from app.repository.log_cache_repository import LOG_CACHE_TTL, LogCacheRepository
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest
from app.schemas.stats_schemas import LogStats


def _sample_log(
    user_id: PydanticObjectId | None = None,
    movie_id: PydanticObjectId | None = None,
) -> Log:
    return Log(
        userId=user_id or PydanticObjectId(),
        movieId=movie_id or PydanticObjectId(),
        tmdbId=550,
        dateWatched=datetime(2024, 1, 2, tzinfo=UTC),
        viewingNotes="Cached viewing",
        posterPath="/poster.jpg",
        watchedWhere="streaming",
    )


def _mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.invalidate_pattern = AsyncMock(return_value=1)
    return cache


def _mock_log_repository() -> MagicMock:
    repository = MagicMock()
    repository.create_log = AsyncMock()
    repository.find_log_by_id = AsyncMock()
    repository.update_log = AsyncMock()
    repository.find_logs_by_user_id = AsyncMock()
    repository.find_logs_by_movie_id = AsyncMock()
    repository.delete_log = AsyncMock()
    repository.get_log_stats = AsyncMock()
    return repository


def test_build_user_logs_key_includes_filters():
    user_id = PydanticObjectId()
    repository = LogCacheRepository(_mock_log_repository())

    key = repository.build_user_logs_key(
        user_id=user_id,
        watched_where="cinema",
        date_watched_from=date(2024, 1, 1),
        date_watched_to=date(2024, 12, 31),
        sort_by="watchedWhere",
        sort_order="asc",
    )

    assert key == (f"cinelog:logs:user:{user_id}:where:cinema:from:2024-01-01:to:2024-12-31:sort:watchedWhere:asc")


@pytest.mark.asyncio
async def test_find_log_by_id_cache_hit_skips_repository(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_log(log)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_log_by_id(str(log.id), log.user_id)

    assert result is not None
    assert result.id == log.id
    inner_repository.find_log_by_id.assert_not_awaited()
    cache.get.assert_awaited_once_with(repository.build_log_key(str(log.id), log.user_id))


@pytest.mark.asyncio
async def test_find_log_by_id_cache_miss_queries_repository_and_sets_cache(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.find_log_by_id.return_value = log
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_log_by_id(str(log.id), log.user_id)

    expected_key = repository.build_log_key(str(log.id), log.user_id)
    assert result == log
    inner_repository.find_log_by_id.assert_awaited_once_with(str(log.id), log.user_id)
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_log(log), ttl=LOG_CACHE_TTL)


@pytest.mark.asyncio
async def test_find_logs_by_user_id_cache_miss_uses_filter_specific_key(beanie_test_db):
    user_id = PydanticObjectId()
    log = _sample_log(user_id=user_id)
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.find_logs_by_user_id.return_value = [log]
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_logs_by_user_id(
            user_id=user_id,
            watched_where="streaming",
            date_watched_from=date(2024, 1, 1),
            date_watched_to=date(2024, 1, 31),
            sort_by="dateWatched",
            sort_order="desc",
        )

    expected_key = repository.build_user_logs_key(
        user_id=user_id,
        watched_where="streaming",
        date_watched_from=date(2024, 1, 1),
        date_watched_to=date(2024, 1, 31),
        sort_by="dateWatched",
        sort_order="desc",
    )
    assert result == [log]
    inner_repository.find_logs_by_user_id.assert_awaited_once_with(
        user_id=user_id,
        watched_where="streaming",
        date_watched_from=date(2024, 1, 1),
        date_watched_to=date(2024, 1, 31),
        sort_by="dateWatched",
        sort_order="desc",
    )
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_logs([log]), ttl=LOG_CACHE_TTL)


@pytest.mark.asyncio
async def test_find_logs_by_user_id_cache_hit_skips_repository(beanie_test_db):
    user_id = PydanticObjectId()
    log = _sample_log(user_id=user_id)
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_logs([log])

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_logs_by_user_id(user_id=user_id)

    assert len(result) == 1
    assert result[0].id == log.id
    inner_repository.find_logs_by_user_id.assert_not_awaited()
    cache.get.assert_awaited_once_with(repository.build_user_logs_key(user_id=user_id))


@pytest.mark.asyncio
async def test_find_logs_by_movie_id_cache_hit_skips_repository(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_logs([log])

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_logs_by_movie_id(str(log.movie_id), log.user_id)

    assert len(result) == 1
    assert result[0].id == log.id
    inner_repository.find_logs_by_movie_id.assert_not_awaited()
    cache.get.assert_awaited_once_with(repository.build_movie_logs_key(str(log.movie_id), log.user_id))


@pytest.mark.asyncio
async def test_find_logs_by_movie_id_cache_miss_queries_repository_and_sets_cache(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.find_logs_by_movie_id.return_value = [log]
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_logs_by_movie_id(str(log.movie_id), log.user_id)

    expected_key = repository.build_movie_logs_key(str(log.movie_id), log.user_id)
    assert result == [log]
    inner_repository.find_logs_by_movie_id.assert_awaited_once_with(str(log.movie_id), log.user_id)
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_logs([log]), ttl=LOG_CACHE_TTL)


@pytest.mark.asyncio
async def test_cache_get_and_set_failures_fall_back_to_repository(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    cache.get.side_effect = RuntimeError("redis down")
    cache.set.side_effect = RuntimeError("redis down")
    inner_repository = _mock_log_repository()
    inner_repository.find_log_by_id.return_value = log
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_log_by_id(str(log.id), log.user_id)

    expected_key = repository.build_log_key(str(log.id), log.user_id)
    assert result == log
    cache.get.assert_awaited_once_with(expected_key)
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_log(log), ttl=LOG_CACHE_TTL)
    inner_repository.find_log_by_id.assert_awaited_once_with(str(log.id), log.user_id)


@pytest.mark.asyncio
async def test_create_log_invalidates_user_and_movie_lists(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.create_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    request = LogCreateRequest(
        movie_id=str(log.movie_id),
        tmdb_id=log.tmdb_id,
        date_watched=log.date_watched.date(),
        watched_where=log.watched_where,
    )

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.create_log(log.user_id, request)

    assert result == log
    cache.invalidate_pattern.assert_has_awaits(
        [
            call(repository.build_user_logs_pattern(log.user_id)),
            call(repository.build_movie_logs_pattern(log.movie_id)),
        ]
    )
    assert cache.invalidate_pattern.await_count == 2


@pytest.mark.asyncio
async def test_update_log_invalidates_id_user_and_movie_cache(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.update_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    request = LogUpdateRequest(viewing_notes="Updated")

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.update_log(str(log.id), log.user_id, request)

    assert result == log
    cache.delete.assert_awaited_once_with(repository.build_log_key(str(log.id), log.user_id))
    cache.invalidate_pattern.assert_has_awaits(
        [
            call(repository.build_user_logs_pattern(log.user_id)),
            call(repository.build_movie_logs_pattern(log.movie_id)),
        ]
    )
    assert cache.invalidate_pattern.await_count == 2


@pytest.mark.asyncio
async def test_update_log_uses_database_lookup_without_reading_cache(beanie_test_db):
    log = _sample_log()
    await log.insert()
    cache = _mock_cache()
    repository = LogCacheRepository()
    cache.get.return_value = repository._serialize_log(log)
    request = LogUpdateRequest(viewing_notes="Updated from DB")

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.update_log(str(log.id), log.user_id, request)

    assert result is not None
    assert result.viewing_notes == "Updated from DB"
    cache.get.assert_not_awaited()
    cache.delete.assert_awaited_once_with(repository.build_log_key(str(log.id), log.user_id))


@pytest.mark.asyncio
async def test_delete_log_invalidates_only_after_successful_delete(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.delete_log.return_value = log
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.delete_log(str(log.id), log.user_id)

    assert result == log
    inner_repository.find_log_by_id.assert_not_awaited()
    inner_repository.delete_log.assert_awaited_once_with(str(log.id), log.user_id)
    cache.delete.assert_awaited_once_with(repository.build_log_key(str(log.id), log.user_id))
    cache.invalidate_pattern.assert_has_awaits(
        [
            call(repository.build_user_logs_pattern(log.user_id)),
            call(repository.build_movie_logs_pattern(log.movie_id)),
        ]
    )
    assert cache.invalidate_pattern.await_count == 2


@pytest.mark.asyncio
async def test_delete_log_uses_database_lookup_without_reading_cache(beanie_test_db):
    log = _sample_log()
    await log.insert()
    cache = _mock_cache()
    repository = LogCacheRepository()
    cache.get.return_value = repository._serialize_log(log)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.delete_log(str(log.id), log.user_id)

    assert result is not None
    assert await Log.get(log.id) is None
    cache.get.assert_not_awaited()
    cache.delete.assert_awaited_once_with(repository.build_log_key(str(log.id), log.user_id))


@pytest.mark.asyncio
async def test_delete_log_not_found_skips_invalidation(beanie_test_db):
    user_id = PydanticObjectId()
    log_id = str(PydanticObjectId())
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.delete_log.return_value = None
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.delete_log(log_id, user_id)

    assert result is None
    inner_repository.delete_log.assert_awaited_once_with(log_id, user_id)
    cache.delete.assert_not_awaited()
    cache.invalidate_pattern.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_log_stats_delegates_to_inner_repository(beanie_test_db):
    user_id = PydanticObjectId()
    stats = LogStats()
    inner_repository = _mock_log_repository()
    inner_repository.get_log_stats.return_value = stats
    repository = LogCacheRepository(inner_repository)

    result = await repository.get_log_stats(user_id, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31))

    assert result == stats
    inner_repository.get_log_stats.assert_awaited_once_with(
        user_id,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 12, 31),
    )


@pytest.mark.asyncio
async def test_invalidation_failure_does_not_raise(beanie_test_db):
    log = _sample_log()
    cache = _mock_cache()
    cache.invalidate_pattern.side_effect = RuntimeError("redis down")
    inner_repository = _mock_log_repository()
    inner_repository.create_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    request = LogCreateRequest(
        movie_id=str(log.movie_id),
        tmdb_id=log.tmdb_id,
        date_watched=log.date_watched.date(),
        watched_where=log.watched_where,
    )

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.create_log(log.user_id, request)

    assert result == log
    cache.invalidate_pattern.assert_has_awaits(
        [
            call(repository.build_user_logs_pattern(log.user_id)),
            call(repository.build_movie_logs_pattern(log.movie_id)),
        ]
    )
    assert cache.invalidate_pattern.await_count == 2
