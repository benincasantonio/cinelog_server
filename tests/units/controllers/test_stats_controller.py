import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app import app
from app.schemas.stats_schemas import StatsResponse
from app.dependencies.auth_dependency import auth_dependency


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_auth_token():
    return "Bearer mock_valid_token"


class TestStatsController:
    """Tests for stats controller endpoints."""

    @patch('app.controllers.stats_controller.stats_service.get_user_stats')
    @patch('app.controllers.stats_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_my_stats_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_stats,
        client,
        mock_auth_token
    ):
        """Test successful stats retrieval."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_get_stats.return_value = {
            "summary": {
                "total_watches": 10,
                "unique_titles": 8,
                "total_rewatches": 2,
                "total_minutes": 1200,
                "vote_average": 7.5
            },
            "distribution": {
                "by_method": {
                    "cinema": 5,
                    "streaming": 3,
                    "home_video": 1,
                    "tv": 1,
                    "other": 0
                }
            },
            "pace": {
                "on_track_for": 50,
                "current_average": 2.5,
                "days_since_last_log": 3
            }
        }

        response = client.get(
            "/v1/stats/me",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["totalWatches"] == 10
        assert data["summary"]["uniqueTitles"] == 8

    @patch('app.controllers.stats_controller.stats_service.get_user_stats')
    @patch('app.controllers.stats_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_my_stats_with_year_filter(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_stats,
        client,
        mock_auth_token
    ):
        """Test stats retrieval with year filters."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"
        mock_get_stats.return_value = {
            "summary": {"total_watches": 5, "unique_titles": 5, "total_rewatches": 0, "total_minutes": 600, "vote_average": None},
            "distribution": {"by_method": {"cinema": 2, "streaming": 3, "home_video": 0, "tv": 0, "other": 0}},
            "pace": {"on_track_for": 0, "current_average": 0.0, "days_since_last_log": 0}
        }

        # Override auth dependency
        app.dependency_overrides[auth_dependency] = lambda: True

        response = client.get(
            "/v1/stats/me?yearFrom=2023&yearTo=2024",
            headers={"Authorization": mock_auth_token}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        mock_get_stats.assert_called_once_with(user_id="user123", year_from=2023, year_to=2024)

    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    @patch('app.controllers.stats_controller.get_user_id_from_token')
    def test_get_my_stats_invalid_year_range(
        self,
        mock_get_user_id,
        mock_verify_token,
        client,
        mock_auth_token
    ):
        """Test stats with invalid year range (yearFrom > yearTo)."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"

        # Override auth dependency
        app.dependency_overrides[auth_dependency] = lambda: True

        response = client.get(
            "/v1/stats/me?yearFrom=2024&yearTo=2023",
            headers={"Authorization": mock_auth_token}
        )
        
        app.dependency_overrides = {}

        assert response.status_code == 400
        assert "yearFrom cannot be greater than yearTo" in response.json()["detail"]

    def test_get_my_stats_unauthorized(self, client):
        """Test stats without authentication."""
        response = client.get("/v1/stats/me")
        assert response.status_code == 401
