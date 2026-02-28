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
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"

class TestStatsController:
    """Tests for stats controller endpoints."""

    @patch('app.controllers.stats_controller.stats_service.get_user_stats')
    def test_get_my_stats_success(
        self,
        mock_get_stats,
        client,
        override_auth
    ):
        """Test successful stats retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth
        
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
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["totalWatches"] == 10
        assert data["summary"]["uniqueTitles"] == 8

    @patch('app.controllers.stats_controller.stats_service.get_user_stats')
    def test_get_my_stats_with_year_filter(
        self,
        mock_get_stats,
        client,
        override_auth
    ):
        """Test stats retrieval with year filters."""
        app.dependency_overrides[auth_dependency] = override_auth
        
        mock_get_stats.return_value = {
            "summary": {"total_watches": 5, "unique_titles": 5, "total_rewatches": 0, "total_minutes": 600, "vote_average": None},
            "distribution": {"by_method": {"cinema": 2, "streaming": 3, "home_video": 0, "tv": 0, "other": 0}},
            "pace": {"on_track_for": 0, "current_average": 0.0, "days_since_last_log": 0}
        }

        response = client.get(
            "/v1/stats/me?yearFrom=2023&yearTo=2024",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        mock_get_stats.assert_called_once_with(user_id="user123", year_from=2023, year_to=2024)

    def test_get_my_stats_invalid_year_range(
        self,
        client,
        override_auth
    ):
        """Test stats with invalid year range (yearFrom > yearTo)."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.get(
            "/v1/stats/me?yearFrom=2024&yearTo=2023",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 422
        messages = [e["msg"] for e in response.json()["detail"]]
        assert any("yearFrom cannot be greater than yearTo" in m for m in messages)

    def test_get_my_stats_only_year_from(self, client, override_auth):
        """Test stats with only yearFrom provided (yearTo required)."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.get(
            "/v1/stats/me?yearFrom=2020",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 422
        messages = [e["msg"] for e in response.json()["detail"]]
        assert any("both" in m.lower() for m in messages)

    def test_get_my_stats_only_year_to(self, client, override_auth):
        """Test stats with only yearTo provided (yearFrom required)."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.get(
            "/v1/stats/me?yearTo=2024",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 422
        messages = [e["msg"] for e in response.json()["detail"]]
        assert any("both" in m.lower() for m in messages)

    def test_get_my_stats_year_out_of_bounds(self, client, override_auth):
        """Test stats with a year outside the valid range."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.get(
            "/v1/stats/me?yearFrom=1800&yearTo=1801",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 422
        messages = [e["msg"] for e in response.json()["detail"]]
        assert any("1888" in m for m in messages)

    def test_get_my_stats_unauthorized(self, client):
        """Test stats without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/stats/me")
        assert response.status_code == 401

    @patch('app.controllers.stats_controller.stats_service.get_user_stats')
    def test_get_my_stats_not_implemented(
        self,
        mock_get_stats,
        client,
        override_auth
    ):
        """Test stats returns 501 when NotImplementedError is raised."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_stats.side_effect = NotImplementedError("Stats not implemented")

        response = client.get(
            "/v1/stats/me",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 501
        assert "Stats endpoint not implemented yet" in response.json()["detail"]

    @patch('app.controllers.stats_controller.stats_service.get_user_stats')
    def test_get_my_stats_app_exception(
        self,
        mock_get_stats,
        client,
        override_auth
    ):
        """Test stats re-raises AppException."""
        from app.utils.exceptions import AppException
        from app.utils.error_codes import ErrorCodes
        
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_stats.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get(
            "/v1/stats/me",
            cookies={"__Host-access_token": "token"}
        )
        
        app.dependency_overrides = {}

        # AppException returns its own error code
        assert response.status_code == ErrorCodes.USER_NOT_FOUND.error_code

