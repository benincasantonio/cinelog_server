import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import date

from app import app
from app.schemas.user_schemas import UserResponse
from app.dependencies.auth_dependency import auth_dependency
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"


class TestUserController:
    """Tests for user controller endpoints."""

    @patch('app.controllers.user_controller.user_service.get_user_info')
    def test_get_user_info_success(
        self,
        mock_get_user_info,
        client,
        override_auth
    ):
        """Test successful user info retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth
        
        # Return actual UserResponse object
        mock_get_user_info.return_value = UserResponse(
            id="user123",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            bio="A bio",
            date_of_birth=date(1990, 1, 1),
            firebase_uid="firebase_uid",
            firebase_data=None
        )

        response = client.get(
            "/v1/users/info",
            cookies={"access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "John"
        mock_get_user_info.assert_called_once_with("user123")

    def test_get_user_info_unauthorized(self, client):
        """Test user info without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/users/info")
        assert response.status_code == 401

    @patch('app.controllers.user_controller.user_service.get_user_info')
    def test_get_user_info_not_found(
        self,
        mock_get_user_info,
        client,
        override_auth
    ):
        """Test user info retrieval when user not found."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_user_info.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get(
            "/v1/users/info",
            cookies={"access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 404

    @patch('app.controllers.user_controller.log_service.get_user_logs')
    def test_get_user_logs_success(
        self,
        mock_get_user_logs,
        client,
        override_auth
    ):
        """Test successful user logs retrieval."""
        from app.schemas.log_schemas import LogListResponse
        
        app.dependency_overrides[auth_dependency] = override_auth

        # Return actual LogListResponse object
        mock_get_user_logs.return_value = LogListResponse(logs=[])

        response = client.get(
            "/v1/users/user123/logs",
            cookies={"access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        mock_get_user_logs.assert_called_once()

    def test_get_user_logs_unauthorized(self, client):
        """Test user logs without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/users/user123/logs")
        assert response.status_code == 401
