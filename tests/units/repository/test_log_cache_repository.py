from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

from app.models.log_model import Log
from app.repository.log_cache_repository import LOG_CACHE_TTL, LogCacheRepository
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest


def _sample_log(
    user_id: UUID | None = None,
    movie_id: UUID | None = None,
) -> Log:
    return Log(
        id=uuid4(),
        user_id=user_id or uuid4(),
        movie_id=movie_id or uuid4(),
        tmdb_id=550,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        viewing_notes="Cached viewing",
        poster_path="/poster.jpg",
        watched_where="streaming",
        deleted=False,
        deleted_at=None,
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
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
    return repository


def test_build_user_logs_key_includes_filters():
    user_id = uuid4()
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


def test_serialize_deserialize_round_trip_preserves_log_fields():
    log = _sample_log()
    repository = LogCacheRepository(_mock_log_repository())

    payload = repository._serialize_log(log)
    restored = repository._deserialize_log(payload)

    assert isinstance(payload["id"], str)
    assert restored.id == log.id
    assert restored.user_id == log.user_id
    assert restored.movie_id == log.movie_id
    assert restored.tmdb_id == log.tmdb_id
    assert restored.date_watched == log.date_watched
    assert restored.viewing_notes == log.viewing_notes
    assert restored.poster_path == log.poster_path
    assert restored.watched_where == log.watched_where
    assert restored.deleted == log.deleted
    assert restored.deleted_at == log.deleted_at
    assert restored.created_at == log.created_at
    assert restored.updated_at == log.updated_at


@pytest.mark.asyncio
async def test_find_log_by_id_cache_hit_skips_repository():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_log(log)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_log_by_id(log.id, log.user_id)

    assert result is not None
    assert result.id == log.id
    inner_repository.find_log_by_id.assert_not_awaited()
    cache.get.assert_awaited_once_with(repository.build_log_key(log.id, log.user_id))


@pytest.mark.asyncio
async def test_find_log_by_id_cache_miss_queries_repository_and_sets_cache():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.find_log_by_id.return_value = log
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_log_by_id(log.id, log.user_id)

    expected_key = repository.build_log_key(log.id, log.user_id)
    assert result == log
    inner_repository.find_log_by_id.assert_awaited_once_with(log.id, log.user_id)
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_log(log), ttl=LOG_CACHE_TTL)


@pytest.mark.asyncio
async def test_find_logs_by_user_id_cache_miss_uses_filter_specific_key():
    user_id = uuid4()
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
async def test_find_logs_by_user_id_cache_hit_skips_repository():
    user_id = uuid4()
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
async def test_find_logs_by_movie_id_cache_hit_skips_repository():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_logs([log])

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_logs_by_movie_id(log.movie_id, log.user_id)

    assert len(result) == 1
    assert result[0].id == log.id
    inner_repository.find_logs_by_movie_id.assert_not_awaited()
    cache.get.assert_awaited_once_with(repository.build_movie_logs_key(log.movie_id, log.user_id))


@pytest.mark.asyncio
async def test_find_logs_by_movie_id_cache_miss_queries_repository_and_sets_cache():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.find_logs_by_movie_id.return_value = [log]
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_logs_by_movie_id(log.movie_id, log.user_id)

    expected_key = repository.build_movie_logs_key(log.movie_id, log.user_id)
    assert result == [log]
    inner_repository.find_logs_by_movie_id.assert_awaited_once_with(log.movie_id, log.user_id)
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_logs([log]), ttl=LOG_CACHE_TTL)


@pytest.mark.asyncio
async def test_cache_get_and_set_failures_fall_back_to_repository():
    log = _sample_log()
    cache = _mock_cache()
    cache.get.side_effect = RuntimeError("redis down")
    cache.set.side_effect = RuntimeError("redis down")
    inner_repository = _mock_log_repository()
    inner_repository.find_log_by_id.return_value = log
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.find_log_by_id(log.id, log.user_id)

    expected_key = repository.build_log_key(log.id, log.user_id)
    assert result == log
    cache.get.assert_awaited_once_with(expected_key)
    cache.set.assert_awaited_once_with(expected_key, repository._serialize_log(log), ttl=LOG_CACHE_TTL)
    inner_repository.find_log_by_id.assert_awaited_once_with(log.id, log.user_id)


@pytest.mark.asyncio
async def test_create_log_invalidates_user_and_movie_lists():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.create_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    request = LogCreateRequest(
        movie_id=log.movie_id,
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
async def test_update_log_invalidates_id_user_and_movie_cache():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.update_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    request = LogUpdateRequest(rating=9)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.update_log(log.id, log.user_id, request)

    assert result == log
    cache.delete.assert_awaited_once_with(repository.build_log_key(log.id, log.user_id))
    cache.invalidate_pattern.assert_has_awaits(
        [
            call(repository.build_user_logs_pattern(log.user_id)),
            call(repository.build_movie_logs_pattern(log.movie_id)),
        ]
    )
    assert cache.invalidate_pattern.await_count == 2


@pytest.mark.asyncio
async def test_update_log_failure_does_not_invalidate_cache():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.update_log.side_effect = RuntimeError("database failure")
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        with pytest.raises(RuntimeError):
            await repository.update_log(log.id, log.user_id, LogUpdateRequest(rating=9))

    cache.delete.assert_not_awaited()
    cache.invalidate_pattern.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_log_uses_repository_lookup_without_reading_cache():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.update_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_log(log)
    request = LogUpdateRequest(viewing_notes="Updated from DB")

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.update_log(log.id, log.user_id, request)

    assert result is not None
    inner_repository.update_log.assert_awaited_once_with(log.id, log.user_id, request)
    cache.get.assert_not_awaited()
    cache.delete.assert_awaited_once_with(repository.build_log_key(log.id, log.user_id))


@pytest.mark.asyncio
async def test_delete_log_invalidates_only_after_successful_delete():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.delete_log.return_value = log
    repository = LogCacheRepository(inner_repository)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.delete_log(log.id, log.user_id)

    assert result == log
    inner_repository.find_log_by_id.assert_not_awaited()
    inner_repository.delete_log.assert_awaited_once_with(log.id, log.user_id)
    cache.delete.assert_awaited_once_with(repository.build_log_key(log.id, log.user_id))
    cache.invalidate_pattern.assert_has_awaits(
        [
            call(repository.build_user_logs_pattern(log.user_id)),
            call(repository.build_movie_logs_pattern(log.movie_id)),
        ]
    )
    assert cache.invalidate_pattern.await_count == 2


@pytest.mark.asyncio
async def test_delete_log_uses_repository_lookup_without_reading_cache():
    log = _sample_log()
    cache = _mock_cache()
    inner_repository = _mock_log_repository()
    inner_repository.delete_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    cache.get.return_value = repository._serialize_log(log)

    with patch("app.repository.log_cache_repository.CacheService.get_instance", return_value=cache):
        result = await repository.delete_log(log.id, log.user_id)

    assert result is not None
    inner_repository.delete_log.assert_awaited_once_with(log.id, log.user_id)
    cache.get.assert_not_awaited()
    cache.delete.assert_awaited_once_with(repository.build_log_key(log.id, log.user_id))


@pytest.mark.asyncio
async def test_delete_log_not_found_skips_invalidation():
    user_id = uuid4()
    log_id = uuid4()
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
async def test_invalidation_failure_does_not_raise():
    log = _sample_log()
    cache = _mock_cache()
    cache.invalidate_pattern.side_effect = RuntimeError("redis down")
    inner_repository = _mock_log_repository()
    inner_repository.create_log.return_value = log
    repository = LogCacheRepository(inner_repository)
    request = LogCreateRequest(
        movie_id=log.movie_id,
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
