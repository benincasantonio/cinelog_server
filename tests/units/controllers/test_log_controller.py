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


from app.dependencies.auth_dependency import auth_dependency
from app.utils.exceptions import AppException

@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"

class TestCreateLog:
    """Tests for POST /v1/logs endpoint."""

    @patch('app.controllers.log_controller.log_service.create_log')
    def test_create_log_success(
        self,
        mock_create_log,
        client,
        sample_log_create_request,
        sample_log_response,
        override_auth
    ):
        """Test successful log creation."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_create_log.return_value = sample_log_response

        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request,
            headers={"Authorization": "Bearer token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "log123"
        mock_create_log.assert_called_once()

    def test_create_log_unauthorized(self, client, sample_log_create_request):
        """Test log creation without authentication."""
        app.dependency_overrides = {} # Ensure no override
        response = client.post(
            "/v1/logs/",
            json=sample_log_create_request
        )

        assert response.status_code == 401

    def test_create_log_invalid_watched_where(
        self,
        client,
        override_auth
    ):
        """Test log creation with invalid watchedWhere value."""
        app.dependency_overrides[auth_dependency] = override_auth

        invalid_request = {
            "movieId": "507f1f77bcf86cd799439011",
            "tmdbId": 550,
            "dateWatched": "2024-01-15",
            "watchedWhere": "invalid_location"
        }

        response = client.post(
            "/v1/logs/",
            json=invalid_request,
            headers={"Authorization": "Bearer token"}
        )
        
        app.dependency_overrides = {}

        assert response.status_code == 422  # Validation error


class TestUpdateLog:
    """Tests for PUT /v1/logs/{log_id} endpoint."""

    @patch('app.controllers.log_controller.log_service.update_log')
    def test_update_log_success(
        self,
        mock_update_log,
        client,
        sample_log_response,
        override_auth
    ):
        """Test successful log update."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_update_log.return_value = sample_log_response

        update_request = {
            "viewingNotes": "Updated notes",
            "watchedWhere": "streaming"
        }

        response = client.put(
            "/v1/logs/log123",
            json=update_request,
            headers={"Authorization": "Bearer token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "log123"
        mock_update_log.assert_called_once()

    def test_update_log_unauthorized(self, client):
        """Test log update without authentication."""
        app.dependency_overrides = {}
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
    def test_get_logs_success(
        self,
        mock_get_logs,
        client,
        sample_log_list_response,
        override_auth
    ):
        """Test successful log list retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_logs.return_value = sample_log_list_response

        response = client.get(
            "/v1/logs/",
            headers={"Authorization": "Bearer token"}
        )
        
        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        mock_get_logs.assert_called_once()

    @patch('app.controllers.log_controller.log_service.get_user_logs')
    def test_get_logs_with_filters(
        self,
        mock_get_logs,
        client,
        sample_log_list_response,
        override_auth
    ):
        """Test log list retrieval with filters."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_logs.return_value = sample_log_list_response

        response = client.get(
            "/v1/logs/?sort_by=dateWatched&sort_order=asc&watched_where=cinema",
            headers={"Authorization": "Bearer token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        mock_get_logs.assert_called_once()

    def test_get_logs_unauthorized(self, client):
        """Test log list retrieval without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/logs/")

        assert response.status_code == 401

