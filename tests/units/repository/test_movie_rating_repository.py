import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from bson import ObjectId

from app.repository.movie_rating_repository import MovieRatingRepository


class TestMovieRatingRepository:
    """Tests for MovieRatingRepository."""

    @patch('app.repository.movie_rating_repository.MovieRating')
    def test_find_movie_rating_by_user_and_movie(self, mock_movie_rating):
        """Test finding a movie rating by user and movie ID."""
        mock_rating = Mock()
        mock_movie_rating.objects.return_value.first.return_value = mock_rating

        result = MovieRatingRepository.find_movie_rating_by_user_and_movie("user123", "movie123")

        assert result == mock_rating
        mock_movie_rating.objects.assert_called_once_with(userId="user123", movieId="movie123")

    @patch('app.repository.movie_rating_repository.MovieRating')
    def test_find_movie_rating_by_user_and_movie_not_found(self, mock_movie_rating):
        """Test when movie rating is not found."""
        mock_movie_rating.objects.return_value.first.return_value = None

        result = MovieRatingRepository.find_movie_rating_by_user_and_movie("user123", "movie456")

        assert result is None

    @patch('app.repository.movie_rating_repository.MovieRating')
    def test_find_movie_rating_by_user_and_tmdb(self, mock_movie_rating):
        """Test finding a movie rating by user and TMDB ID."""
        mock_rating = Mock()
        mock_movie_rating.objects.return_value.first.return_value = mock_rating

        repo = MovieRatingRepository()
        result = repo.find_movie_rating_by_user_and_tmdb("user123", "550")

        assert result == mock_rating
        mock_movie_rating.objects.assert_called_once_with(userId="user123", tmdbId="550")

    @patch('app.repository.movie_rating_repository.MovieRatingRepository.find_movie_rating_by_user_and_movie')
    @patch('app.repository.movie_rating_repository.MovieRating')
    def test_create_movie_rating_new(self, mock_movie_rating_class, mock_find):
        """Test creating a new movie rating."""
        mock_find.return_value = None  # No existing rating
        
        mock_new_rating = Mock()
        mock_movie_rating_class.return_value = mock_new_rating

        result = MovieRatingRepository.create_update_movie_rating(
            user_id="user123",
            movie_id="movie123",
            rating=8,
            comment="Great movie!",
            tmdb_id=550
        )

        assert result == mock_new_rating
        mock_new_rating.save.assert_called_once()

    @patch('app.repository.movie_rating_repository.MovieRatingRepository.find_movie_rating_by_user_and_movie')
    def test_update_movie_rating_existing(self, mock_find):
        """Test updating an existing movie rating."""
        mock_existing = Mock()
        mock_find.return_value = mock_existing

        result = MovieRatingRepository.create_update_movie_rating(
            user_id="user123",
            movie_id="movie123",
            rating=9,
            comment="Even better on rewatch!",
            tmdb_id=550
        )

        assert result == mock_existing
        assert mock_existing.rating == 9
        assert mock_existing.review == "Even better on rewatch!"
        mock_existing.save.assert_called_once()
