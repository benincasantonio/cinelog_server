import pytest
from unittest.mock import AsyncMock, Mock
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

        mock_logs = [
            {
                "movieId": "movie1",
                "watchedWhere": "cinema",
                "movie": mock_movie,
                "movieRating": 8,
            },
            {
                "movieId": "movie2",
                "watchedWhere": "streaming",
                "movie": mock_movie,
                "movieRating": 7,
            },
            {
                "movieId": "movie1",
                "watchedWhere": "tv",
                "movie": mock_movie,
                "movieRating": 9,
            },  # Rewatch
        ]
        mock_log_repository.find_logs_by_user_id.return_value = mock_logs

        result = await stats_service.get_user_stats("user123")

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

        await stats_service.get_user_stats("user123", year_from=2023, year_to=2024)

        # Verify the request was made with proper date filters
        call_args = mock_log_repository.find_logs_by_user_id.call_args
        assert call_args is not None
        request = call_args.kwargs.get("request")
        assert request is not None
        assert str(request.date_watched_from) == "2023-01-01"
        assert str(request.date_watched_to) == "2024-12-31"

    def test_compute_summary_with_invalid_runtime(self, stats_service):
        """Test compute_summary handles invalid runtime gracefully."""
        logs = [
            {"movieId": "movie1", "movie": None, "runtime": "invalid"},
        ]

        result = stats_service.compute_summary(logs)

        assert result["total_watches"] == 1
        assert result["total_minutes"] == 0  # Invalid runtime is ignored

    def test_compute_summary_with_none_movie(self, stats_service):
        """Test compute_summary when movie is None but runtime is in log."""
        logs = [
            {"movieId": "movie1", "movie": None, "runtime": 90},
        ]

        result = stats_service.compute_summary(logs)

        assert result["total_minutes"] == 90

    def test_compute_distribution_all_methods(self, stats_service):
        """Test distribution computation for all watch methods."""
        logs = [
            {"watchedWhere": "cinema"},
            {"watchedWhere": "streaming"},
            {"watchedWhere": "homeVideo"},
            {"watchedWhere": "tv"},
            {"watchedWhere": "other"},
            {"watchedWhere": "cinema"},  # Second cinema
        ]

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
        logs = [
            {
                "movieId": "movie1",
                "movie": None,
                "runtime": 100,
                "movieRating": "invalid",
            },
        ]

        result = stats_service.compute_summary(logs)

        assert result["vote_average"] is None  # Invalid rating is ignored
