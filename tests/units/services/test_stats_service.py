import pytest
from datetime import date
from unittest.mock import AsyncMock
from beanie import PydanticObjectId
from app.services.stats_service import StatsService
from app.schemas.stats_schemas import LogStats, LogDistributionEntry
from app.schemas.movie_rating_schemas import MovieRatingStats
from app.schemas.movie_schemas import MovieStats


@pytest.fixture
def mock_log_repository():
    return AsyncMock()


@pytest.fixture
def mock_movie_rating_repository():
    return AsyncMock()


@pytest.fixture
def mock_movie_repository():
    return AsyncMock()


@pytest.fixture
def stats_service(
    mock_log_repository, mock_movie_rating_repository, mock_movie_repository
):
    return StatsService(
        log_repository=mock_log_repository,
        movie_rating_repository=mock_movie_rating_repository,
        movie_repository=mock_movie_repository,
    )


def _empty_log_stats():
    return LogStats()


def _empty_movie_rating_stats():
    return MovieRatingStats(average_rating=0.0, total_ratings=0)


def _empty_movie_stats():
    return MovieStats(total_runtime=0)


class TestStatsService:
    """Tests for StatsService."""

    @pytest.mark.asyncio
    async def test_get_user_stats_empty_logs(
        self,
        stats_service,
        mock_log_repository,
        mock_movie_rating_repository,
        mock_movie_repository,
    ):
        """Test stats with no logs."""
        mock_log_repository.get_log_stats.return_value = _empty_log_stats()
        mock_movie_rating_repository.get_user_movie_ratings_average.return_value = (
            _empty_movie_rating_stats()
        )
        mock_movie_repository.get_movie_stats.return_value = _empty_movie_stats()

        result = await stats_service.get_user_stats(PydanticObjectId())

        assert result.summary.total_watches == 0
        assert result.summary.unique_titles == 0
        assert result.summary.total_rewatches == 0
        assert result.summary.total_minutes == 0
        assert result.summary.vote_average == 0.0
        assert result.distribution.by_method.cinema == 0
        assert result.pace.on_track_for == 0

    @pytest.mark.asyncio
    async def test_get_user_stats_with_logs(
        self,
        stats_service,
        mock_log_repository,
        mock_movie_rating_repository,
        mock_movie_repository,
    ):
        """Test stats with logs."""
        movie_id_1 = PydanticObjectId()
        movie_id_2 = PydanticObjectId()

        mock_log_repository.get_log_stats.return_value = LogStats(
            total_watches=3,
            unique_titles=2,
            unique_movie_ids=[movie_id_1, movie_id_2],
            distribution=[
                LogDistributionEntry(watched_where="cinema", count=1),
                LogDistributionEntry(watched_where="streaming", count=1),
                LogDistributionEntry(watched_where="tv", count=1),
            ],
        )
        mock_movie_rating_repository.get_user_movie_ratings_average.return_value = (
            MovieRatingStats(average_rating=7.666, total_ratings=2)
        )
        mock_movie_repository.get_movie_stats.return_value = MovieStats(
            total_runtime=360
        )

        result = await stats_service.get_user_stats(PydanticObjectId())

        assert result.summary.total_watches == 3
        assert result.summary.unique_titles == 2
        assert result.summary.total_rewatches == 1
        assert result.summary.total_minutes == 360
        assert result.summary.vote_average == pytest.approx(7.666, abs=0.01)

    @pytest.mark.asyncio
    async def test_get_user_stats_with_year_filter(
        self,
        stats_service,
        mock_log_repository,
        mock_movie_rating_repository,
        mock_movie_repository,
    ):
        """Test stats with year filters."""
        mock_log_repository.get_log_stats.return_value = _empty_log_stats()
        mock_movie_rating_repository.get_user_movie_ratings_average.return_value = (
            _empty_movie_rating_stats()
        )
        mock_movie_repository.get_movie_stats.return_value = _empty_movie_stats()

        user_id = PydanticObjectId()
        await stats_service.get_user_stats(user_id, year_from=2023, year_to=2024)

        mock_log_repository.get_log_stats.assert_awaited_once_with(
            user_id,
            date_from=date(2023, 1, 1),
            date_to=date(2024, 12, 31),
        )

    @pytest.mark.asyncio
    async def test_distribution_maps_correctly(
        self,
        stats_service,
        mock_log_repository,
        mock_movie_rating_repository,
        mock_movie_repository,
    ):
        """Test that distribution entries map correctly to StatsByMethod."""
        mock_log_repository.get_log_stats.return_value = LogStats(
            total_watches=7,
            unique_titles=7,
            unique_movie_ids=[PydanticObjectId() for _ in range(7)],
            distribution=[
                LogDistributionEntry(watched_where="cinema", count=2),
                LogDistributionEntry(watched_where="streaming", count=1),
                LogDistributionEntry(watched_where="homeVideo", count=1),
                LogDistributionEntry(watched_where="tv", count=1),
                LogDistributionEntry(watched_where="other", count=2),
            ],
        )
        mock_movie_rating_repository.get_user_movie_ratings_average.return_value = (
            _empty_movie_rating_stats()
        )
        mock_movie_repository.get_movie_stats.return_value = _empty_movie_stats()

        result = await stats_service.get_user_stats(PydanticObjectId())

        assert result.distribution.by_method.cinema == 2
        assert result.distribution.by_method.streaming == 1
        assert result.distribution.by_method.home_video == 1
        assert result.distribution.by_method.tv == 1
        assert result.distribution.by_method.other == 2
