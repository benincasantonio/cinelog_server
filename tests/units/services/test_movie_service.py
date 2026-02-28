import pytest
from unittest.mock import Mock

from app.services.movie_service import MovieService


class TestMovieService:
    """Tests for MovieService."""

    @pytest.fixture
    def mock_movie_repository(self):
        return Mock()

    @pytest.fixture
    def mock_tmdb_service(self):
        return Mock()

    @pytest.fixture
    def movie_service(self, mock_movie_repository, mock_tmdb_service):
        return MovieService(
            movie_repository=mock_movie_repository, tmdb_service=mock_tmdb_service
        )

    def test_get_movie_by_id(self, movie_service, mock_movie_repository):
        """Test getting a movie by ID."""
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie.title = "Test Movie"
        mock_movie_repository.find_movie_by_id.return_value = mock_movie

        result = movie_service.get_movie_by_id("movie123")

        assert result == mock_movie
        mock_movie_repository.find_movie_by_id.assert_called_once_with("movie123")

    def test_get_movie_by_id_not_found(self, movie_service, mock_movie_repository):
        """Test getting a movie by ID when not found."""
        mock_movie_repository.find_movie_by_id.return_value = None

        result = movie_service.get_movie_by_id("nonexistent")

        assert result is None

    def test_get_movie_by_tmdb_id(self, movie_service, mock_movie_repository):
        """Test getting a movie by TMDB ID."""
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie.tmdb_id = 550
        mock_movie_repository.find_movie_by_tmdb_id.return_value = mock_movie

        result = movie_service.get_movie_by_tmdb_id(550)

        assert result == mock_movie
        mock_movie_repository.find_movie_by_tmdb_id.assert_called_once_with(550)

    def test_find_or_create_movie_exists(
        self, movie_service, mock_movie_repository, mock_tmdb_service
    ):
        """Test find_or_create when movie already exists."""
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie_repository.find_movie_by_tmdb_id.return_value = mock_movie

        result = movie_service.find_or_create_movie(550)

        assert result == mock_movie
        # Should not call TMDB API since movie exists
        mock_tmdb_service.get_movie_details.assert_not_called()

    def test_find_or_create_movie_creates_new(
        self, movie_service, mock_movie_repository, mock_tmdb_service
    ):
        """Test find_or_create when movie doesn't exist."""
        mock_movie_repository.find_movie_by_tmdb_id.return_value = None

        mock_tmdb_data = Mock()
        mock_tmdb_data.title = "Fight Club"
        mock_tmdb_service.get_movie_details.return_value = mock_tmdb_data

        mock_new_movie = Mock()
        mock_movie_repository.create_from_tmdb_data.return_value = mock_new_movie

        result = movie_service.find_or_create_movie(550)

        assert result == mock_new_movie
        mock_tmdb_service.get_movie_details.assert_called_once_with(550)
        mock_movie_repository.create_from_tmdb_data.assert_called_once_with(
            mock_tmdb_data
        )
