import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from app import app
from app.schemas.movie_rating_schemas import MovieRatingResponse


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_auth_token():
    return "Bearer mock_valid_token"


class TestMovieRatingController:
    """Tests for movie rating controller endpoints."""

    @patch('app.controllers.movie_rating_controller.movie_rating_service.create_update_movie_rating')
    @patch('app.controllers.movie_rating_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_create_movie_rating_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_create_rating,
        client,
        mock_auth_token
    ):
        """Test creating a movie rating."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        
        mock_create_rating.return_value = MovieRatingResponse(
            id="rating123",
            userId="user123",
            movieId="movie123",
            tmdbId="550",
            rating=8,
            comment="Great movie!",
            createdAt=datetime.now(),
            updatedAt=datetime.now()
        )

        response = client.post(
            "/v1/movie-ratings/",
            json={
                "tmdbId": "550",
                "rating": 8,
                "comment": "Great movie!"
            },
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8

    def test_create_movie_rating_unauthorized(self, client):
        """Test creating movie rating without authentication."""
        response = client.post(
            "/v1/movie-ratings/",
            json={
                "tmdbId": "550",
                "rating": 8,
                "comment": "Great movie!"
            }
        )
        assert response.status_code == 401

    @patch('app.controllers.movie_rating_controller.movie_rating_service.get_movie_ratings_by_tmdb_id')
    @patch('app.controllers.movie_rating_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_movie_rating_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_rating,
        client,
        mock_auth_token
    ):
        """Test getting a movie rating."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        
        mock_get_rating.return_value = MovieRatingResponse(
            id="rating123",
            userId="user123",
            movieId="movie123",
            tmdbId="550",
            rating=8,
            comment="Great movie!",
            createdAt=datetime.now(),
            updatedAt=datetime.now()
        )

        response = client.get(
            "/v1/movie-ratings/550",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8

    @patch('app.controllers.movie_rating_controller.movie_rating_service.get_movie_ratings_by_tmdb_id')
    @patch('app.controllers.movie_rating_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_movie_rating_not_found(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_rating,
        client,
        mock_auth_token
    ):
        """Test getting a movie rating that doesn't exist."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_get_rating.return_value = None

        response = client.get(
            "/v1/movie-ratings/999",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 404

    @patch('app.controllers.movie_rating_controller.movie_rating_service.get_movie_ratings_by_tmdb_id')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_movie_rating_with_user_id_param(
        self,
        mock_verify_token,
        mock_get_rating,
        client,
        mock_auth_token
    ):
        """Test getting a movie rating with explicit user_id parameter."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        
        mock_get_rating.return_value = MovieRatingResponse(
            id="rating123",
            userId="other_user",
            movieId="movie123",
            tmdbId="550",
            rating=9,
            comment="Amazing!",
            createdAt=datetime.now(),
            updatedAt=datetime.now()
        )

        response = client.get(
            "/v1/movie-ratings/550?user_id=other_user",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        mock_get_rating.assert_called_once_with(user_id="other_user", tmdb_id=550)

    def test_get_movie_rating_unauthorized(self, client):
        """Test getting movie rating without authentication."""
        response = client.get("/v1/movie-ratings/550")
        assert response.status_code == 401
