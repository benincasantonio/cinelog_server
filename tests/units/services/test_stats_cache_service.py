import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId

from app.services.stats_cache_service import StatsCacheService, STATS_CACHE_TTL
from app.schemas.stats_schemas import (
    StatsResponse,
    StatsSummary,
    StatsDistribution,
    StatsByMethod,
    StatsPace,
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
        distribution=StatsDistribution(
            by_method=StatsByMethod(cinema=2, streaming=1, home_video=1, tv=1, other=0)
        ),
        pace=StatsPace(on_track_for=0, current_average=0.0, days_since_last_log=0),
    )


class TestBuildKey:
    def test_no_filters(self):
        uid = PydanticObjectId()
        assert StatsCacheService.build_key(uid) == f"cinelog:stats:{uid}:all"

    def test_both_filters(self):
        uid = PydanticObjectId()
        assert (
            StatsCacheService.build_key(uid, 2023, 2024)
            == f"cinelog:stats:{uid}:2023:2024"
        )

    def test_only_year_from(self):
        uid = PydanticObjectId()
        assert (
            StatsCacheService.build_key(uid, year_from=2023)
            == f"cinelog:stats:{uid}:2023:any"
        )

    def test_only_year_to(self):
        uid = PydanticObjectId()
        assert (
            StatsCacheService.build_key(uid, year_to=2024)
            == f"cinelog:stats:{uid}:any:2024"
        )


class TestGetStats:
    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)

        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = StatsCacheService()
            result = await service.get_stats(PydanticObjectId())
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_stats_response(self):
        stats = _sample_stats_response()
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=stats.model_dump(mode="json"))

        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = StatsCacheService()
            result = await service.get_stats(PydanticObjectId())
            assert result is not None
            assert isinstance(result, StatsResponse)
            assert result.summary.total_watches == 5

    @pytest.mark.asyncio
    async def test_cache_not_initialized_returns_none(self):
        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            side_effect=RuntimeError("CacheService not initialized"),
        ):
            service = StatsCacheService()
            result = await service.get_stats(PydanticObjectId())
            assert result is None


class TestSetStats:
    @pytest.mark.asyncio
    async def test_set_stats_calls_cache_set(self):
        stats = _sample_stats_response()
        uid = PydanticObjectId()
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)

        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = StatsCacheService()
            await service.set_stats(uid, 2023, 2024, stats=stats)

            expected_key = f"cinelog:stats:{uid}:2023:2024"
            mock_cache.set.assert_awaited_once_with(
                expected_key,
                stats.model_dump(mode="json"),
                ttl=STATS_CACHE_TTL,
            )

    @pytest.mark.asyncio
    async def test_set_stats_cache_not_initialized(self):
        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            side_effect=RuntimeError("CacheService not initialized"),
        ):
            # Should not raise
            service = StatsCacheService()
            await service.set_stats(PydanticObjectId(), stats=_sample_stats_response())


class TestInvalidateUserStats:
    @pytest.mark.asyncio
    async def test_invalidate_calls_pattern(self):
        uid = PydanticObjectId()
        mock_cache = MagicMock()
        mock_cache.invalidate_pattern = AsyncMock(return_value=3)

        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            return_value=mock_cache,
        ):
            service = StatsCacheService()
            await service.invalidate_user_stats(uid)
            mock_cache.invalidate_pattern.assert_awaited_once_with(
                f"cinelog:stats:{uid}:*"
            )

    @pytest.mark.asyncio
    async def test_invalidate_cache_not_initialized(self):
        with patch(
            "app.services.stats_cache_service.CacheService.get_instance",
            side_effect=RuntimeError("CacheService not initialized"),
        ):
            # Should not raise
            service = StatsCacheService()
            await service.invalidate_user_stats(PydanticObjectId())
