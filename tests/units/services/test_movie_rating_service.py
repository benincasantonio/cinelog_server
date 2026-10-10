from datetime import datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.services.movie_rating_service import MovieRatingService


@pytest.fixture
def mock_movie_rating_repository():
    return AsyncMock()


@pytest.fixture
def mock_movie_service():
    return AsyncMock()


@pytest.fixture
def mock_stats_cache_service():
    return AsyncMock()


@pytest.fixture
def mock_log_list_cache_service():
    return AsyncMock()


@pytest.fixture
def movie_rating_service(
    mock_movie_rating_repository,
    mock_movie_service,
    mock_log_list_cache_service,
    mock_stats_cache_service,
):
    return MovieRatingService(
        movie_rating_repository=mock_movie_rating_repository,
        movie_service=mock_movie_service,
        log_list_cache_service=mock_log_list_cache_service,
        stats_cache_service=mock_stats_cache_service,
    )


def _mock_rating(user_id: UUID | str, rating: int = 9):
    rating_obj = Mock()
    rating_obj.id = "rating123"
    rating_obj.user_id = str(user_id)
    rating_obj.movie_id = "movie123"
    rating_obj.rating = rating
    rating_obj.review = "Excellent!"
    rating_obj.created_at = datetime.now()
    rating_obj.updated_at = datetime.now()
    return rating_obj


class TestMovieRatingService:
    """Tests for MovieRatingService."""

    @pytest.mark.asyncio
    async def test_create_update_movie_rating(
        self, movie_rating_service, mock_movie_rating_repository, mock_movie_service, mock_log_list_cache_service
    ):
        """Test creating/updating a movie rating."""
        # Setup mocks
        mock_movie = Mock()
        mock_movie.id = uuid4()
        mock_movie.tmdb_id = 550
        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_rating = Mock()
        mock_rating.id = "rating123"
        mock_rating.user_id = "user123"
        mock_rating.movie_id = "movie123"
        mock_rating.rating = 8
        mock_rating.review = "Great movie!"
        mock_rating.created_at = datetime.now()
        mock_rating.updated_at = datetime.now()

        mock_movie_rating_repository.create_update_movie_rating.return_value = mock_rating

        # Execute
        user_id = uuid4()
        result = await movie_rating_service.create_update_movie_rating(
            user_id, tmdb_id=550, rating=8, comment="Great movie!"
        )

        # Verify
        assert result.id == "rating123"
        assert result.rating == 8
        assert result.comment == "Great movie!"
        assert result.tmdb_id == 550
        mock_movie_service.find_or_create_movie.assert_awaited_once_with(tmdb_id=550)
        mock_movie_rating_repository.create_update_movie_rating.assert_awaited_once_with(
            user_id=user_id,
            movie_id=mock_movie.id,
            rating=8,
            comment="Great movie!",
        )
        mock_log_list_cache_service.invalidate_user.assert_awaited_once_with(user_id)

    @pytest.mark.asyncio
    async def test_create_update_movie_rating_invalidates_stats_cache(
        self,
        movie_rating_service,
        mock_movie_rating_repository,
        mock_movie_service,
        mock_stats_cache_service,
    ):
        """Test that creating/updating a rating invalidates the stats cache."""
        user_id = uuid4()
        mock_movie = Mock()
        mock_movie.id = uuid4()
        mock_movie.tmdb_id = 550
        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_rating = Mock()
        mock_rating.id = "rating123"
        mock_rating.user_id = str(user_id)
        mock_rating.movie_id = "movie123"
        mock_rating.rating = 8
        mock_rating.review = "Great!"
        mock_rating.created_at = datetime.now()
        mock_rating.updated_at = datetime.now()
        mock_movie_rating_repository.create_update_movie_rating.return_value = mock_rating

        await movie_rating_service.create_update_movie_rating(user_id=user_id, tmdb_id=550, rating=8, comment="Great!")

        mock_stats_cache_service.invalidate_user_stats.assert_awaited_once_with(user_id)

    @pytest.mark.asyncio
    async def test_failed_rating_write_does_not_invalidate_log_list(
        self, movie_rating_service, mock_movie_rating_repository, mock_movie_service, mock_log_list_cache_service
    ):
        mock_movie_service.find_or_create_movie.return_value = Mock(id=uuid4())
        mock_movie_rating_repository.create_update_movie_rating.side_effect = RuntimeError("database failure")

        with pytest.raises(RuntimeError):
            await movie_rating_service.create_update_movie_rating(user_id=uuid4(), tmdb_id=550, rating=8)

        mock_log_list_cache_service.invalidate_user.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_movie_ratings_by_tmdb_id_returns_rating(
        self, movie_rating_service, mock_movie_rating_repository, mock_movie_service
    ):
        """Owner reads own rating by tmdb_id, resolved through the movie."""
        user_id = uuid4()
        movie = Mock(id=uuid4(), tmdb_id=550)
        mock_movie_service.get_movie_by_tmdb_id.return_value = movie
        mock_movie_rating_repository.find_movie_rating_by_user_and_movie.return_value = _mock_rating(user_id)

        result = await movie_rating_service.get_movie_ratings_by_tmdb_id(user_id=user_id, tmdb_id=550)

        assert result is not None
        assert result.rating == 9
        assert result.tmdb_id == 550
        mock_movie_service.get_movie_by_tmdb_id.assert_awaited_once_with(550)
        mock_movie_rating_repository.find_movie_rating_by_user_and_movie.assert_awaited_once_with(
            user_id=user_id, movie_id=movie.id
        )

    @pytest.mark.asyncio
    async def test_get_movie_ratings_by_tmdb_id_returns_none_for_unknown_movie(
        self, movie_rating_service, mock_movie_rating_repository, mock_movie_service
    ):
        """Returns None without querying ratings when the movie is not in the catalog."""
        mock_movie_service.get_movie_by_tmdb_id.return_value = None

        result = await movie_rating_service.get_movie_ratings_by_tmdb_id(user_id=uuid4(), tmdb_id=550)

        assert result is None
        mock_movie_rating_repository.find_movie_rating_by_user_and_movie.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_movie_ratings_by_tmdb_id_not_found(
        self, movie_rating_service, mock_movie_rating_repository, mock_movie_service
    ):
        """Returns None when no rating exists for the caller."""
        mock_movie_service.get_movie_by_tmdb_id.return_value = Mock(id=uuid4(), tmdb_id=550)
        mock_movie_rating_repository.find_movie_rating_by_user_and_movie.return_value = None

        result = await movie_rating_service.get_movie_ratings_by_tmdb_id(user_id=uuid4(), tmdb_id=550)

        assert result is None
