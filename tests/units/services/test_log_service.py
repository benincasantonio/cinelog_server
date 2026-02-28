import pytest
from unittest.mock import Mock, MagicMock
from datetime import date
from app.services.log_service import LogService
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest, LogListRequest
from app.utils.exceptions import AppException


@pytest.fixture
def mock_log_repository():
    return Mock()


@pytest.fixture
def mock_movie_service():
    return Mock()


@pytest.fixture
def log_service(mock_log_repository, mock_movie_service):
    return LogService(log_repository=mock_log_repository, movie_service=mock_movie_service)


class TestLogService:
    """Tests for LogService."""

    def test_create_log_success(self, log_service, mock_log_repository, mock_movie_service):
        """Test successful log creation."""
        # Setup mocks
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = date(2020, 1, 1)
        mock_movie.overview = "A description"
        mock_movie.vote_average = 8.5
        mock_movie.runtime = 120
        mock_movie.original_language = "en"
        mock_movie.created_at = date(2020, 1, 1)
        mock_movie.updated_at = date(2020, 1, 1)

        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Great movie!"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "cinema"

        mock_log_repository.create_log.return_value = mock_log

        # Execute
        request = LogCreateRequest(
            tmdb_id=550,
            date_watched=date(2024, 1, 15),
            viewing_notes="Great movie!",
            watched_where="cinema"
        )
        result = log_service.create_log("user123", request)

        # Verify
        assert result.id == "log123"
        assert result.movie_id == "movie123"
        assert result.movie.title == "Test Movie"
        mock_movie_service.find_or_create_movie.assert_called_once_with(tmdb_id=550)
        mock_log_repository.create_log.assert_called_once()

    def test_create_log_auto_populate_poster(self, log_service, mock_log_repository, mock_movie_service):
        """Test that posterPath is auto-populated from movie if not provided."""
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/movie_poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None

        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = None
        mock_log.poster_path = "/movie_poster.jpg"
        mock_log.watched_where = "streaming"

        mock_log_repository.create_log.return_value = mock_log

        request = LogCreateRequest(
            tmdb_id=550,
            date_watched=date(2024, 1, 15),
            watched_where="streaming"
            # posterPath not provided
        )
        result = log_service.create_log("user123", request)

        # Verify posterPath was populated from movie
        assert result.poster_path == "/movie_poster.jpg"

    def test_update_log_success(self, log_service, mock_log_repository, mock_movie_service):
        """Test successful log update."""
        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Updated notes"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "streaming"

        mock_log_repository.update_log.return_value = mock_log

        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None

        mock_movie_service.get_movie_by_id.return_value = mock_movie

        request = LogUpdateRequest(viewing_notes="Updated notes")
        result = log_service.update_log("user123", "log123", request)

        assert result.viewing_notes == "Updated notes"
        mock_log_repository.update_log.assert_called_once()

    def test_update_log_not_found(self, log_service, mock_log_repository):
        """Test update log when log is not found."""
        mock_log_repository.update_log.return_value = None

        request = LogUpdateRequest(viewing_notes="Updated notes")

        with pytest.raises(AppException):
            log_service.update_log("user123", "nonexistent_log", request)

    def test_get_user_logs(self, log_service, mock_log_repository, mock_movie_service):
        """Test getting user logs."""
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None

        mock_log_repository.find_logs_by_user_id.return_value = [
            {
                "id": "log123",
                "movieId": "movie123",
                "movie": mock_movie,
                "tmdbId": 550,
                "dateWatched": date(2024, 1, 15),
                "viewingNotes": "Great!",
                "posterPath": "/poster.jpg",
                "watchedWhere": "cinema",
                "movieRating": 8
            }
        ]

        request = LogListRequest(sort_by="dateWatched", sort_order="desc")
        result = log_service.get_user_logs("user123", request)

        assert len(result.logs) == 1
        assert result.logs[0].id == "log123"
        assert result.logs[0].movie_rating == 8

    def test_map_movie_to_response_none(self, log_service):
        """Test _map_movie_to_response with None movie."""
        result = log_service._map_movie_to_response(None)
        assert result is None
