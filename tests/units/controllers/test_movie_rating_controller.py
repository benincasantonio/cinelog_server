from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_movie_rating_service
from app.schemas.movie_rating_schemas import MovieRatingResponse

# Released response fields read by cinelog_web. A rename or removal must fail here.
MOVIE_RATING_RESPONSE_FIELDS = {"id", "userId", "movieId", "tmdbId", "rating", "comment", "createdAt", "updatedAt"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"


class TestMovieRatingController:
    """Tests for movie rating controller endpoints."""

    @patch.object(get_movie_rating_service(), "create_update_movie_rating", new_callable=AsyncMock)
    def test_create_movie_rating_success(self, mock_create_rating, client, override_auth):
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
            updated_at=datetime.now(),
        )

        response = client.post(
            "/v1/movie-ratings/",
            json={"tmdbId": "550", "rating": 8, "comment": "Great movie!"},
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
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
            json={"tmdbId": "550", "rating": 8, "comment": "Great movie!"},
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )
        assert response.status_code == 401

    @patch.object(get_movie_rating_service(), "get_movie_ratings_by_tmdb_id", new_callable=AsyncMock)
    def test_get_movie_rating_success(self, mock_get_rating, client, override_auth):
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
            updated_at=datetime.now(),
        )

        response = client.get("/v1/movie-ratings/550", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8

    @patch.object(get_movie_rating_service(), "get_movie_ratings_by_tmdb_id", new_callable=AsyncMock)
    def test_get_movie_rating_not_found(self, mock_get_rating, client, override_auth):
        """Test getting a movie rating that doesn't exist returns 204."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_rating.return_value = None

        response = client.get("/v1/movie-ratings/999", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 204

    def test_get_movie_rating_unauthorized(self, client):
        """Test getting movie rating without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/movie-ratings/550")
        assert response.status_code == 401


def _rating_response() -> MovieRatingResponse:
    return MovieRatingResponse(
        id="rating123",
        user_id="user123",
        movie_id="movie123",
        tmdb_id=550,
        rating=8,
        comment=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestMovieRatingResponseFields:
    """The serialized rating responses keep every released field name."""

    @patch.object(get_movie_rating_service(), "create_update_movie_rating", new_callable=AsyncMock)
    def test_create_movie_rating_response_fields(self, mock_create_rating, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_create_rating.return_value = _rating_response()

        response = client.post(
            "/v1/movie-ratings/",
            json={"tmdbId": 550, "rating": 8},
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        assert set(response.json()) == MOVIE_RATING_RESPONSE_FIELDS

    @patch.object(get_movie_rating_service(), "get_movie_ratings_by_tmdb_id", new_callable=AsyncMock)
    def test_get_movie_rating_response_fields(self, mock_get_rating, client, override_auth):
        """The route has response_model=None, so no declared model shapes this response."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_rating.return_value = _rating_response()

        response = client.get("/v1/movie-ratings/550", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 200
        assert set(response.json()) == MOVIE_RATING_RESPONSE_FIELDS
