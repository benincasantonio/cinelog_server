import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from app import app
from app.schemas.movie_rating_schemas import MovieRatingResponse


@pytest.fixture
def client():
    return TestClient(app)

from app.dependencies.auth_dependency import auth_dependency

@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"

class TestMovieRatingController:
    """Tests for movie rating controller endpoints."""

    @patch('app.controllers.movie_rating_controller.movie_rating_service.create_update_movie_rating')
    def test_create_movie_rating_success(
        self,
        mock_create_rating,
        client,
        override_auth
    ):
        """Test creating a movie rating."""
        app.dependency_overrides[auth_dependency] = override_auth
        
        mock_create_rating.return_value = MovieRatingResponse(
            id="rating123",
            user_id="user123",
            movie_id="movie123",
            tmdb_id="550",
            rating=8,
            comment="Great movie!",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        response = client.post(
            "/v1/movie-ratings/",
            json={
                "tmdbId": "550",
                "rating": 8,
                "comment": "Great movie!"
            },
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8

    def test_create_movie_rating_unauthorized(self, client):
        """Test creating movie rating without authentication."""
        app.dependency_overrides = {}
        response = client.post(
            "/v1/movie-ratings/",
            json={
                "tmdbId": "550",
                "rating": 8,
                "comment": "Great movie!"
            },
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"}
        )
        assert response.status_code == 401

    @patch('app.controllers.movie_rating_controller.movie_rating_service.get_movie_ratings_by_tmdb_id')
    def test_get_movie_rating_success(
        self,
        mock_get_rating,
        client,
        override_auth
    ):
        """Test getting a movie rating."""
        app.dependency_overrides[auth_dependency] = override_auth
        
        mock_get_rating.return_value = MovieRatingResponse(
            id="rating123",
            user_id="user123",
            movie_id="movie123",
            tmdb_id="550",
            rating=8,
            comment="Great movie!",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        response = client.get(
            "/v1/movie-ratings/550",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8

    @patch('app.controllers.movie_rating_controller.movie_rating_service.get_movie_ratings_by_tmdb_id')
    def test_get_movie_rating_not_found(
        self,
        mock_get_rating,
        client,
        override_auth
    ):
        """Test getting a movie rating that doesn't exist."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_rating.return_value = None

        response = client.get(
            "/v1/movie-ratings/999",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 404

    @patch('app.controllers.movie_rating_controller.movie_rating_service.get_movie_ratings_by_tmdb_id')
    def test_get_movie_rating_with_user_id_param(
        self,
        mock_get_rating,
        client,
        override_auth
    ):
        """Test getting a movie rating with explicit user_id parameter."""
        # Even with explicit user_id, we might need auth if the endpoint requires it.
        # Checking implementation: endpoints use auth_dependency.
        app.dependency_overrides[auth_dependency] = override_auth
        
        mock_get_rating.return_value = MovieRatingResponse(
            id="rating123",
            user_id="other_user",
            movie_id="movie123",
            tmdb_id="550",
            rating=9,
            comment="Amazing!",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        response = client.get(
            "/v1/movie-ratings/550?user_id=other_user",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        mock_get_rating.assert_called_once_with(user_id="other_user", tmdb_id=550)

    def test_get_movie_rating_unauthorized(self, client):
        """Test getting movie rating without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/movie-ratings/550")
        assert response.status_code == 401

