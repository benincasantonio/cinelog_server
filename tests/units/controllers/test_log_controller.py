from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi.testclient import TestClient

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_log_service
from app.schemas.log_schemas import (
    LogCreateResponse,
    LogListItem,
    LogListResponse,
)
from app.schemas.movie_schemas import MovieResponse
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_log_create_request():
    """Sample log creation request."""
    return {
        "movieId": "507f1f77bcf86cd799439011",
        "tmdbId": 550,
        "dateWatched": "2024-01-15",
        "viewingNotes": "Amazing film!",
        "posterPath": "/path/to/poster.jpg",
        "watchedWhere": "cinema",
    }


@pytest.fixture
def sample_movie_response():
    """Sample movie response for log responses."""
    return MovieResponse(
        id=PydanticObjectId(),
        title="Fight Club",
        tmdb_id=550,
        poster_path="/path/to/poster.jpg",
        release_date=None,
        overview="A description",
        vote_average=8.5,
        runtime=139,
        original_language="en",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def sample_log_response(sample_movie_response):
    """Sample log response."""
    return LogCreateResponse(
        id=str(PydanticObjectId()),
        movie_id=str(PydanticObjectId()),
        movie=sample_movie_response,
        tmdb_id=550,
        date_watched=date(2024, 1, 15),
        viewing_notes="Amazing film!",
        poster_path="/path/to/poster.jpg",
        watched_where="cinema",
    )


@pytest.fixture
def sample_log_list_response(sample_movie_response):
    """Sample log list response."""
    return LogListResponse(
        logs=[
            LogListItem(
                id=PydanticObjectId(),
                movie_id=PydanticObjectId(),
                movie=sample_movie_response,
                tmdb_id=550,
                date_watched=date(2024, 1, 15),
                viewing_notes="Amazing film!",
                poster_path="/path/to/poster.jpg",
                watched_where="cinema",
                movie_rating=8,
            )
        ],
    )


@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: PydanticObjectId()


class TestCreateLog:
    """Tests for POST /v1/logs endpoint."""

    @patch.object(get_log_service(), "create_log", new_callable=AsyncMock)
    def test_create_log_success(
        self,
        mock_create_log,
        client,
        sample_log_create_request,
        sample_log_response,
        override_auth,
    ):
        """Test successful log creation."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_create_log.return_value = sample_log_response

        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request,
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "movieId" in data
        mock_create_log.assert_called_once()

    def test_create_log_unauthorized(self, client, sample_log_create_request):
        """Test log creation without authentication."""
        app.dependency_overrides = {}  # Ensure no override
        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request,
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        assert response.status_code == 401

    def test_create_log_invalid_watched_where(self, client, override_auth):
        """Test log creation with invalid watchedWhere value."""
        app.dependency_overrides[auth_dependency] = override_auth

        invalid_request = {
            "movieId": "507f1f77bcf86cd799439011",
            "tmdbId": 550,
            "dateWatched": "2024-01-15",
            "watchedWhere": "invalid_location",
        }

        response = client.post(
            "/v1/logs/",
            json=invalid_request,
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 422  # Validation error


class TestUpdateLog:
    """Tests for PUT /v1/logs/{log_id} endpoint."""

    @patch.object(get_log_service(), "update_log", new_callable=AsyncMock)
    def test_update_log_success(self, mock_update_log, client, sample_log_response, override_auth):
        """Test successful log update."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_update_log.return_value = sample_log_response

        update_request = {"viewingNotes": "Updated notes", "watchedWhere": "streaming"}

        response = client.put(
            "/v1/logs/507f1f77bcf86cd799439011",
            json=update_request,
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        mock_update_log.assert_called_once()

    def test_update_log_unauthorized(self, client):
        """Test log update without authentication."""
        app.dependency_overrides = {}
        update_request = {"viewingNotes": "Updated notes"}

        response = client.put(
            "/v1/logs/507f1f77bcf86cd799439011",
            json=update_request,
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        assert response.status_code == 401

    def test_update_log_invalid_object_id_returns_422(self, client, override_auth):
        """Malformed log_id path param fails FastAPI validation with 422."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.put(
            "/v1/logs/not-an-object-id",
            json={"viewingNotes": "x"},
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 422


class TestDeleteLog:
    """Tests for DELETE /v1/logs/{log_id} endpoint."""

    @patch.object(get_log_service(), "delete_log", new_callable=AsyncMock)
    def test_delete_log_success_returns_204(self, mock_delete_log, client, override_auth):
        """Successful deletion returns 204 No Content with empty body."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_delete_log.return_value = None

        response = client.delete(
            "/v1/logs/507f1f77bcf86cd799439011",
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 204
        assert response.content == b""
        mock_delete_log.assert_called_once()

    @patch.object(get_log_service(), "delete_log", new_callable=AsyncMock)
    def test_delete_log_not_found_returns_404(self, mock_delete_log, client, override_auth):
        """Deleting a missing or non-owned log returns 404."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_delete_log.side_effect = AppException(ErrorCodes.LOG_NOT_FOUND)

        response = client.delete(
            "/v1/logs/507f1f77bcf86cd799439011",
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 404
        assert response.json()["error_code_name"] == ErrorCodes.LOG_NOT_FOUND.error_code_name

    def test_delete_log_unauthorized(self, client):
        """Delete without access token returns 401."""
        app.dependency_overrides = {}
        response = client.delete(
            "/v1/logs/507f1f77bcf86cd799439011",
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        assert response.status_code == 401

    def test_delete_log_invalid_object_id_returns_422(self, client, override_auth):
        """Malformed log_id path param fails FastAPI validation with 422."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.delete(
            "/v1/logs/not-an-object-id",
            cookies={"__Host-access_token": "token", "__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 422


class TestGetLogsByHandle:
    """Tests for GET /v1/logs/{handle} endpoint."""

    @patch.object(get_log_service(), "get_user_logs_by_handle", new_callable=AsyncMock)
    def test_get_logs_by_handle_success(self, mock_get_logs_by_handle, client, sample_log_list_response, override_auth):
        """Test successful log list retrieval by handle."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_logs_by_handle.return_value = sample_log_list_response

        response = client.get("/v1/logs/johndoe", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        mock_get_logs_by_handle.assert_called_once()

    def test_get_logs_by_handle_unauthorized(self, client):
        """Test log list retrieval without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/logs/johndoe")

        assert response.status_code == 401

    @patch.object(get_log_service(), "get_user_logs_by_handle", new_callable=AsyncMock)
    def test_get_logs_by_handle_profile_not_public(self, mock_get_logs_by_handle, client, override_auth):
        """Test log list retrieval for private profile."""
        from app.utils.error_codes_utils import ErrorCodes
        from app.utils.exceptions_utils import AppException

        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_logs_by_handle.side_effect = AppException(ErrorCodes.PROFILE_NOT_PUBLIC)

        response = client.get("/v1/logs/johndoe", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 403

    @patch.object(get_log_service(), "get_user_logs_by_handle", new_callable=AsyncMock)
    def test_get_logs_by_handle_user_not_found(self, mock_get_logs_by_handle, client, override_auth):
        """Test log list retrieval for nonexistent user."""
        from app.utils.error_codes_utils import ErrorCodes
        from app.utils.exceptions_utils import AppException

        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_logs_by_handle.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get("/v1/logs/nonexistent", cookies={"__Host-access_token": "token"})

        app.dependency_overrides = {}

        assert response.status_code == 404
