from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_movie_rating_service
from app.schemas.movie_rating_schemas import MovieRatingResponse
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException

# Response fields read by cinelog_web. A rename or removal must fail here.
MOVIE_RATING_RESPONSE_FIELDS = {"id", "userId", "movieId", "rating", "comment", "createdAt", "updatedAt"}
MOVIE_ID = uuid4()
CSRF_COOKIES = {"__Host-access_token": "token", "__Host-csrf_token": "test-token"}
CSRF_HEADERS = {"X-CSRF-Token": "test-token"}


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
            rating=8,
            comment="Great movie!",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        response = client.post(
            "/v1/movie-ratings/",
            json={"movieId": str(MOVIE_ID), "rating": 8, "comment": "Great movie!"},
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8
        mock_create_rating.assert_awaited_once_with(
            user_id="user123", comment="Great movie!", rating=8, movie_id=MOVIE_ID
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"tmdbId": 550, "rating": 8},
            {"movieId": str(MOVIE_ID), "tmdbId": 550, "rating": 8},
            {"movieId": "550", "rating": 8},
            {"rating": 8},
        ],
    )
    @patch.object(get_movie_rating_service(), "create_update_movie_rating", new_callable=AsyncMock)
    def test_create_movie_rating_rejects_legacy_or_invalid_identity(
        self, mock_create_rating, client, override_auth, payload
    ):
        """tmdbId is rejected even beside a valid movieId; nothing is written."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.post("/v1/movie-ratings/", json=payload, cookies=CSRF_COOKIES, headers=CSRF_HEADERS)

        app.dependency_overrides = {}

        assert response.status_code == 422
        mock_create_rating.assert_not_awaited()

    def test_create_movie_rating_unauthorized(self, client):
        """Test creating movie rating without authentication."""
        app.dependency_overrides = {}
        response = client.post(
            "/v1/movie-ratings/",
            json={"movieId": str(MOVIE_ID), "rating": 8, "comment": "Great movie!"},
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )
        assert response.status_code == 401

    @patch.object(get_movie_rating_service(), "get_movie_rating", new_callable=AsyncMock)
    def test_get_movie_rating_success(self, mock_get_rating, client, override_auth):
        """Test getting a movie rating."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_rating.return_value = MovieRatingResponse(
            id="rating123",
            user_id="user123",
            movie_id="movie123",
            rating=8,
            comment="Great movie!",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        response = client.get(f"/v1/movie-ratings/{MOVIE_ID}", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 8

    @patch.object(get_movie_rating_service(), "get_movie_rating", new_callable=AsyncMock)
    def test_get_movie_rating_not_found(self, mock_get_rating, client, override_auth):
        """Test getting a movie rating that doesn't exist returns 204."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_rating.return_value = None

        response = client.get(f"/v1/movie-ratings/{uuid4()}", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 204

    @pytest.mark.parametrize("movie_id", ["550", "not-a-uuid"])
    @patch.object(get_movie_rating_service(), "get_movie_rating", new_callable=AsyncMock)
    def test_get_movie_rating_rejects_numeric_and_malformed_ids(self, mock_get_rating, client, override_auth, movie_id):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.get(f"/v1/movie-ratings/{movie_id}", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 422
        mock_get_rating.assert_not_awaited()

    @patch.object(get_movie_rating_service(), "get_movie_rating", new_callable=AsyncMock)
    def test_get_movie_rating_unknown_movie_is_404(self, mock_get_rating, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_rating.side_effect = AppException(ErrorCodes.MOVIE_NOT_FOUND)

        response = client.get(f"/v1/movie-ratings/{uuid4()}", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 404

    def test_get_movie_rating_unauthorized(self, client):
        """Test getting movie rating without authentication."""
        app.dependency_overrides = {}
        response = client.get(f"/v1/movie-ratings/{MOVIE_ID}")
        assert response.status_code == 401


def _rating_response() -> MovieRatingResponse:
    return MovieRatingResponse(
        id="rating123",
        user_id="user123",
        movie_id="movie123",
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
            json={"movieId": str(MOVIE_ID), "rating": 8},
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        assert set(response.json()) == MOVIE_RATING_RESPONSE_FIELDS

    @patch.object(get_movie_rating_service(), "get_movie_rating", new_callable=AsyncMock)
    def test_get_movie_rating_response_fields(self, mock_get_rating, client, override_auth):
        """The route has response_model=None, so no declared model shapes this response."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_rating.return_value = _rating_response()

        response = client.get(f"/v1/movie-ratings/{MOVIE_ID}", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 200
        assert set(response.json()) == MOVIE_RATING_RESPONSE_FIELDS
