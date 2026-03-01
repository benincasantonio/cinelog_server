import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from app.services.movie_rating_service import MovieRatingService


@pytest.fixture
def mock_movie_rating_repository():
    return AsyncMock()


@pytest.fixture
def mock_movie_service():
    return AsyncMock()


@pytest.fixture
def movie_rating_service(mock_movie_rating_repository, mock_movie_service):
    return MovieRatingService(
        movie_rating_repository=mock_movie_rating_repository,
        movie_service=mock_movie_service,
    )


class TestMovieRatingService:
    """Tests for MovieRatingService."""

    @pytest.mark.asyncio
    async def test_create_update_movie_rating(
        self, movie_rating_service, mock_movie_rating_repository, mock_movie_service
    ):
        """Test creating/updating a movie rating."""
        # Setup mocks
        mock_movie = Mock()
        mock_movie.id = "movie123"
        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_rating = Mock()
        mock_rating.id = "rating123"
        mock_rating.user_id = "user123"
        mock_rating.movie_id = "movie123"
        mock_rating.tmdb_id = 550
        mock_rating.rating = 8
        mock_rating.review = "Great movie!"
        mock_rating.created_at = datetime.now()
        mock_rating.updated_at = datetime.now()

        mock_movie_rating_repository.create_update_movie_rating.return_value = (
            mock_rating
        )

        # Execute
        result = await movie_rating_service.create_update_movie_rating(
            user_id="user123", tmdb_id="550", rating=8, comment="Great movie!"
        )

        # Verify
        assert result.id == "rating123"
        assert result.rating == 8
        assert result.comment == "Great movie!"
        mock_movie_service.find_or_create_movie.assert_awaited_once_with(tmdb_id="550")

    @pytest.mark.asyncio
    async def test_get_movie_rating_found(
        self, movie_rating_service, mock_movie_rating_repository
    ):
        """Test getting an existing movie rating."""
        mock_rating = Mock()
        mock_rating.id = "rating123"
        mock_rating.user_id = "user123"
        mock_rating.movie_id = "movie123"
        mock_rating.tmdb_id = 550
        mock_rating.rating = 8
        mock_rating.review = "Great movie!"
        mock_rating.created_at = datetime.now()
        mock_rating.updated_at = datetime.now()

        mock_movie_rating_repository.find_movie_rating_by_user_and_movie.return_value = mock_rating

        result = await movie_rating_service.get_movie_rating("user123", "movie123")

        assert result is not None
        assert result.id == "rating123"
        assert result.rating == 8

    @pytest.mark.asyncio
    async def test_get_movie_rating_not_found(
        self, movie_rating_service, mock_movie_rating_repository
    ):
        """Test getting a movie rating that doesn't exist."""
        mock_movie_rating_repository.find_movie_rating_by_user_and_movie.return_value = None

        result = await movie_rating_service.get_movie_rating("user123", "movie123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_movie_ratings_by_tmdb_id_found(
        self, movie_rating_service, mock_movie_rating_repository
    ):
        """Test getting movie rating by TMDB ID."""
        mock_rating = Mock()
        mock_rating.id = "rating123"
        mock_rating.user_id = "user123"
        mock_rating.movie_id = "movie123"
        mock_rating.tmdb_id = 550
        mock_rating.rating = 9
        mock_rating.review = "Excellent!"
        mock_rating.created_at = datetime.now()
        mock_rating.updated_at = datetime.now()

        mock_movie_rating_repository.find_movie_rating_by_user_and_tmdb.return_value = (
            mock_rating
        )

        result = await movie_rating_service.get_movie_ratings_by_tmdb_id("user123", 550)

        assert result is not None
        assert result.rating == 9

    @pytest.mark.asyncio
    async def test_get_movie_ratings_by_tmdb_id_not_found(
        self, movie_rating_service, mock_movie_rating_repository
    ):
        """Test getting movie rating by TMDB ID when not found."""
        mock_movie_rating_repository.find_movie_rating_by_user_and_tmdb.return_value = (
            None
        )

        result = await movie_rating_service.get_movie_ratings_by_tmdb_id("user123", 550)

        assert result is None
