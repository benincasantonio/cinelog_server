from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.stats_schemas import (
    StatsByMethod,
    StatsDistribution,
    StatsPace,
    StatsResponse,
    StatsSummary,
    UserStatsAggregate,
)
from app.services.stats_service import StatsService


@pytest.fixture
def mock_stats_repository():
    repository = AsyncMock()
    repository.get_user_stats.return_value = UserStatsAggregate()
    return repository


@pytest.fixture
def mock_stats_cache_service():
    cache = AsyncMock()
    cache.get_stats.return_value = None
    return cache


@pytest.fixture
def stats_service(mock_stats_repository, mock_stats_cache_service):
    return StatsService(
        stats_repository=mock_stats_repository,
        stats_cache_service=mock_stats_cache_service,
    )


@pytest.mark.asyncio
async def test_get_user_stats_maps_repository_aggregate(
    stats_service,
    mock_stats_repository,
):
    mock_stats_repository.get_user_stats.return_value = UserStatsAggregate(
        total_watches=3,
        unique_titles=2,
        total_minutes=360,
        vote_average=8.0,
        by_method=StatsByMethod(cinema=1, streaming=1, home_video=0, tv=1, other=0),
    )

    result = await stats_service.get_user_stats(uuid4())

    assert result.summary == StatsSummary(
        total_watches=3,
        unique_titles=2,
        total_rewatches=1,
        total_minutes=360,
        vote_average=8.0,
    )
    assert result.distribution.by_method == StatsByMethod(
        cinema=1,
        streaming=1,
        home_video=0,
        tv=1,
        other=0,
    )
    assert result.pace == StatsPace(on_track_for=0, current_average=0.0, days_since_last_log=0)


@pytest.mark.asyncio
async def test_get_user_stats_preserves_null_vote_average(
    stats_service,
    mock_stats_repository,
):
    mock_stats_repository.get_user_stats.return_value = UserStatsAggregate(vote_average=None)

    result = await stats_service.get_user_stats(uuid4())

    assert result.summary.vote_average is None


@pytest.mark.asyncio
async def test_get_user_stats_converts_year_filters_to_inclusive_dates(
    stats_service,
    mock_stats_repository,
):
    user_id = uuid4()

    await stats_service.get_user_stats(user_id, year_from=2023, year_to=2024)

    mock_stats_repository.get_user_stats.assert_awaited_once_with(
        user_id,
        date_from=date(2023, 1, 1),
        date_to=date(2024, 12, 31),
    )


def _sample_stats_response() -> StatsResponse:
    return StatsResponse(
        summary=StatsSummary(
            total_watches=5,
            unique_titles=3,
            total_rewatches=2,
            total_minutes=600,
            vote_average=7.5,
        ),
        distribution=StatsDistribution(by_method=StatsByMethod(cinema=2, streaming=1, home_video=1, tv=1, other=0)),
        pace=StatsPace(on_track_for=0, current_average=0.0, days_since_last_log=0),
    )


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_response_without_querying_repository(
    stats_service,
    mock_stats_cache_service,
    mock_stats_repository,
):
    cached = _sample_stats_response()
    mock_stats_cache_service.get_stats.return_value = cached

    result = await stats_service.get_user_stats(uuid4())

    assert result is cached
    mock_stats_repository.get_user_stats.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_miss_queries_repository_and_caches_final_response(
    stats_service,
    mock_stats_cache_service,
    mock_stats_repository,
):
    user_id = uuid4()

    result = await stats_service.get_user_stats(user_id)

    mock_stats_repository.get_user_stats.assert_awaited_once_with(
        user_id,
        date_from=None,
        date_to=None,
    )
    mock_stats_cache_service.set_stats.assert_awaited_once_with(
        user_id,
        None,
        None,
        stats=result,
    )
