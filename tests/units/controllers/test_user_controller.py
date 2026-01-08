import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import date

from app import app
from app.schemas.user_schemas import UserResponse


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_auth_token():
    return "Bearer mock_valid_token"


class TestUserController:
    """Tests for user controller endpoints."""

    @patch('app.controllers.user_controller.user_service.get_user_info')
    @patch('app.controllers.user_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_user_info_success(
        self,
        mock_verify_token,
        mock_get_user_id,
        mock_get_user_info,
        client,
        mock_auth_token
    ):
        """Test successful user info retrieval."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.return_value = "user123"

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
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "John"
        mock_get_user_info.assert_called_once_with("user123")

    def test_get_user_info_unauthorized(self, client):
        """Test user info without authentication."""
        response = client.get("/v1/users/info")
        assert response.status_code == 401

    @patch('app.controllers.user_controller.log_service.get_user_logs')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_user_logs_success(
        self,
        mock_verify_token,
        mock_get_user_logs,
        client,
        mock_auth_token
    ):
        """Test successful user logs retrieval."""
        from app.schemas.log_schemas import LogListResponse
        
        mock_verify_token.return_value = {"uid": "firebase_uid"}

        # Return actual LogListResponse object
        mock_get_user_logs.return_value = LogListResponse(logs=[])

        response = client.get(
            "/v1/users/user123/logs",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        mock_get_user_logs.assert_called_once()

    def test_get_user_logs_unauthorized(self, client):
        """Test user logs without authentication."""
        response = client.get("/v1/users/user123/logs")
        assert response.status_code == 401

    @patch('app.controllers.user_controller.get_user_id_from_token')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_user_info_token_extraction_error(
        self,
        mock_verify_token,
        mock_get_user_id,
        client,
        mock_auth_token
    ):
        """Test get user info returns 401 when token extraction fails."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        mock_get_user_id.side_effect = ValueError("Invalid token")

        response = client.get(
            "/v1/users/info",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

