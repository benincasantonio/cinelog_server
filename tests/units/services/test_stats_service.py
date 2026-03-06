import pytest
from datetime import date
from unittest.mock import AsyncMock, Mock
from beanie import PydanticObjectId
from app.services.stats_service import StatsService


@pytest.fixture
def mock_log_repository():
    return AsyncMock()


@pytest.fixture
def stats_service(mock_log_repository):
    return StatsService(log_repository=mock_log_repository)


class TestStatsService:
    """Tests for StatsService."""

    @pytest.mark.asyncio
    async def test_get_user_stats_empty_logs(self, stats_service, mock_log_repository):
        """Test stats with no logs."""
        mock_log_repository.find_logs_by_user_id.return_value = []

        result = await stats_service.get_user_stats("user123")

        assert result["summary"]["total_watches"] == 0
        assert result["summary"]["unique_titles"] == 0
        assert result["summary"]["total_rewatches"] == 0
        assert result["summary"]["total_minutes"] == 0
        assert result["summary"]["vote_average"] is None
        assert result["distribution"]["by_method"]["cinema"] == 0
        assert result["pace"]["on_track_for"] == 0

    @pytest.mark.asyncio
    async def test_get_user_stats_with_logs(self, stats_service, mock_log_repository):
        """Test stats with logs."""
        mock_movie = Mock()
        mock_movie.runtime = 120

        mock_log1 = Mock()
        mock_log1.movie_id = PydanticObjectId()
        mock_log1.watched_where = "cinema"
        mock_log1.movie = mock_movie
        mock_log1.movie_rating = 8
        mock_log1.runtime = 120

        mock_log2 = Mock()
        mock_log2.movie_id = PydanticObjectId()
        mock_log2.watched_where = "streaming"
        mock_log2.movie = mock_movie
        mock_log2.movie_rating = 7
        mock_log2.runtime = 120

        mock_log3 = Mock()
        mock_log3.movie_id = mock_log1.movie_id  # Same as log1 (rewatch)
        mock_log3.watched_where = "tv"
        mock_log3.movie = mock_movie
        mock_log3.movie_rating = 9
        mock_log3.runtime = 120

        mock_logs = [mock_log1, mock_log2, mock_log3]
        mock_log_repository.find_logs_by_user_id.return_value = mock_logs

        result = await stats_service.get_user_stats(PydanticObjectId())

        assert result["summary"]["total_watches"] == 3
        assert result["summary"]["unique_titles"] == 2
        assert result["summary"]["total_rewatches"] == 1
        assert result["summary"]["total_minutes"] == 360  # 3 * 120
        assert result["summary"]["vote_average"] == 8.0  # (8+7+9)/3

    @pytest.mark.asyncio
    async def test_get_user_stats_with_year_filter(
        self, stats_service, mock_log_repository
    ):
        """Test stats with year filters."""
        mock_log_repository.find_logs_by_user_id.return_value = []

        user_id = PydanticObjectId()
        await stats_service.get_user_stats(user_id, year_from=2023, year_to=2024)

        # Verify the request was made with proper date filters
        mock_log_repository.find_logs_by_user_id.assert_awaited_once_with(
            user_id,
            sort_by="dateWatched",
            sort_order="desc",
            watched_where=None,
            date_watched_from=date(2023, 1, 1),
            date_watched_to=date(2024, 12, 31),
        )

    def test_compute_summary_with_invalid_runtime(self, stats_service):
        """Test compute_summary handles invalid runtime gracefully."""
        mock_log = Mock()
        mock_log.movie_id = PydanticObjectId()
        mock_log.movie = None
        mock_log.runtime = "invalid"
        mock_log.movie_rating = None
        logs = [mock_log]

        result = stats_service.compute_summary(logs)

        assert result["total_watches"] == 1
        assert result["total_minutes"] == 0  # Invalid runtime is ignored

    def test_compute_summary_with_none_movie(self, stats_service):
        """Test compute_summary when movie is None but runtime is in log."""
        mock_log = Mock()
        mock_log.movie_id = PydanticObjectId()
        mock_log.movie = None
        mock_log.runtime = 90
        mock_log.movie_rating = None
        logs = [mock_log]

        result = stats_service.compute_summary(logs)

        assert result["total_minutes"] == 90

    def test_compute_distribution_all_methods(self, stats_service):
        """Test distribution computation for all watch methods."""
        logs = []
        for watched_where in [
            "cinema",
            "streaming",
            "homeVideo",
            "tv",
            "other",
            "cinema",
        ]:
            mock_log = Mock()
            mock_log.watched_where = watched_where
            logs.append(mock_log)

        result = stats_service.compute_distribution(logs)

        assert result["by_method"]["cinema"] == 2
        assert result["by_method"]["streaming"] == 1
        assert result["by_method"]["home_video"] == 1
        assert result["by_method"]["tv"] == 1
        assert result["by_method"]["other"] == 1

    def test_compute_distribution_with_object_logs(self, stats_service):
        """Test distribution with object logs instead of dicts."""
        mock_log = Mock()
        mock_log.watched_where = "cinema"

        logs = [mock_log]

        result = stats_service.compute_distribution(logs)

        assert result["by_method"]["cinema"] == 1

    def test_compute_summary_with_invalid_movie_rating(self, stats_service):
        """Test compute_summary handles invalid movie rating gracefully."""
        mock_log = Mock()
        mock_log.movie_id = PydanticObjectId()
        mock_log.movie = None
        mock_log.runtime = 100
        mock_log.movie_rating = "invalid"
        logs = [mock_log]

        result = stats_service.compute_summary(logs)

        assert result["vote_average"] is None  # Invalid rating is ignored
        assert result["total_minutes"] == 100
