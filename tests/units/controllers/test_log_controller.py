import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import date

from app import app
from app.schemas.log_schemas import (
    LogCreateRequest,
    LogCreateResponse,
    LogUpdateRequest,
    LogListResponse,
    LogListItem
)
from app.schemas.movie_schemas import MovieResponse


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_auth_token():
    """Mock JWT token for authentication."""
    return "Bearer mock_valid_token"


@pytest.fixture
def sample_log_create_request():
    """Sample log creation request."""
    return {
        "movieId": "507f1f77bcf86cd799439011",
        "tmdbId": 550,
        "dateWatched": "2024-01-15",
        "viewingNotes": "Amazing film!",
        "posterPath": "/path/to/poster.jpg",
        "watchedWhere": "cinema"
    }


@pytest.fixture
def sample_movie_response():
    """Sample movie response for log responses."""
    return MovieResponse(
        id="507f1f77bcf86cd799439011",
        title="Fight Club",
        tmdb_id=550,
        poster_path="/path/to/poster.jpg",
        release_date=None,
        overview="A description",
        vote_average=8.5,
        runtime=139,
        original_language="en",
    )


@pytest.fixture
def sample_log_response(sample_movie_response):
    """Sample log response."""
    return LogCreateResponse(
        id="log123",
        movie_id="507f1f77bcf86cd799439011",
        movie=sample_movie_response,
        tmdb_id=550,
        date_watched=date(2024, 1, 15),
        viewing_notes="Amazing film!",
        poster_path="/path/to/poster.jpg",
        watched_where="cinema"
    )


@pytest.fixture
def sample_log_list_response(sample_movie_response):
    """Sample log list response."""
    return LogListResponse(
        logs=[
            LogListItem(
                id="log123",
                movie_id="507f1f77bcf86cd799439011",
                movie=sample_movie_response,
                tmdb_id=550,
                date_watched=date(2024, 1, 15),
                viewing_notes="Amazing film!",
                poster_path="/path/to/poster.jpg",
                watched_where="cinema",
                movie_rating=8
            )
        ],
    )


class TestCreateLog:
    """Tests for POST /v1/logs endpoint."""

    @patch('app.controllers.log_controller.log_service.create_log')
    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_create_log_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_create_log,
        client,
        mock_auth_token,
        sample_log_create_request,
        sample_log_response
    ):
        """Test successful log creation."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_create_log.return_value = sample_log_response

        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request,
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "log123"
        assert data["movieId"] == "507f1f77bcf86cd799439011"
        assert data["tmdbId"] == 550
        assert data["watchedWhere"] == "cinema"
        mock_create_log.assert_called_once()

    def test_create_log_unauthorized(self, client, sample_log_create_request):
        """Test log creation without authentication."""
        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request
        )

        assert response.status_code == 401

    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    @patch('app.controllers.log_controller.get_user_id_from_token')
    def test_create_log_invalid_watched_where(
        self,
        mock_get_user_id,
        mock_verify_token,
        client,
        mock_auth_token
    ):
        """Test log creation with invalid watchedWhere value."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"

        invalid_request = {
            "movieId": "507f1f77bcf86cd799439011",
            "tmdbId": 550,
            "dateWatched": "2024-01-15",
            "watchedWhere": "invalid_location"
        }

        response = client.post(
            "/v1/logs/",
            json=invalid_request,
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 422  # Validation error


class TestUpdateLog:
    """Tests for PUT /v1/logs/{log_id} endpoint."""

    @patch('app.controllers.log_controller.log_service.update_log')
    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_update_log_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_update_log,
        client,
        mock_auth_token,
        sample_log_response
    ):
        """Test successful log update."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_update_log.return_value = sample_log_response

        update_request = {
            "viewingNotes": "Updated notes",
            "watchedWhere": "streaming"
        }

        response = client.put(
            "/v1/logs/log123",
            json=update_request,
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "log123"
        mock_update_log.assert_called_once()

    def test_update_log_unauthorized(self, client):
        """Test log update without authentication."""
        update_request = {
            "viewingNotes": "Updated notes"
        }

        response = client.put(
            "/v1/logs/log123",
            json=update_request
        )

        assert response.status_code == 401


class TestGetLogs:
    """Tests for GET /v1/logs endpoint."""

    @patch('app.controllers.log_controller.log_service.get_user_logs')
    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_logs_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_logs,
        client,
        mock_auth_token,
        sample_log_list_response
    ):
        """Test successful log list retrieval."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_get_logs.return_value = sample_log_list_response

        response = client.get(
            "/v1/logs/",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["id"] == "log123"
        mock_get_logs.assert_called_once()

    @patch('app.controllers.log_controller.log_service.get_user_logs')
    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_logs_with_filters(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_logs,
        client,
        mock_auth_token,
        sample_log_list_response
    ):
        """Test log list retrieval with filters."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_get_logs.return_value = sample_log_list_response

        response = client.get(
            "/v1/logs/?sort_by=dateWatched&sort_order=asc&watched_where=cinema",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        mock_get_logs.assert_called_once()

    def test_get_logs_unauthorized(self, client):
        """Test log list retrieval without authentication."""
        response = client.get("/v1/logs/")

        assert response.status_code == 401

    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_logs_token_extraction_error(
        self,
        mock_verify_token,
        mock_get_user_id,
        client,
        mock_auth_token
    ):
        """Test get logs returns 401 when token extraction fails."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.side_effect = ValueError("Invalid token")

        response = client.get(
            "/v1/logs/",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]


class TestLogControllerTokenErrors:
    """Tests for token extraction errors in log controller."""

    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_create_log_token_extraction_error(
        self,
        mock_verify_token,
        mock_get_user_id,
        client,
        mock_auth_token,
        sample_log_create_request
    ):
        """Test create log returns 401 when token extraction fails."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.side_effect = ValueError("Invalid token")

        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request,
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    @patch('app.controllers.log_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_update_log_token_extraction_error(
        self,
        mock_verify_token,
        mock_get_user_id,
        client,
        mock_auth_token
    ):
        """Test update log returns 401 when token extraction fails."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.side_effect = ValueError("Invalid token")

        update_request = {"viewingNotes": "Updated notes"}

        response = client.put(
            "/v1/logs/log123",
            json=update_request,
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

