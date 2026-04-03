import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import date

from app import app
from app.schemas.log_schemas import LogListResponse
from app.schemas.user_schemas import ChangePasswordResponse, PublicProfileResponse, UserResponse
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

    @patch(
        "app.controllers.user_controller.user_service.get_user_info",
        new_callable=AsyncMock,
    )
    def test_get_user_info_success(self, mock_get_user_info, client, override_auth):
        """Test successful user info retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_user_info.return_value = UserResponse(
            id="user123",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            bio="A bio",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="public",
        )

        response = client.get(
            "/v1/users/info", cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "John"
        mock_get_user_info.assert_awaited_once_with("user123")

    def test_get_user_info_unauthorized(self, client):
        """Test user info without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/users/info")
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.get_user_info",
        new_callable=AsyncMock,
    )
    def test_get_user_info_not_found(self, mock_get_user_info, client, override_auth):
        """Test user info retrieval when user not found."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_user_info.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get(
            "/v1/users/info", cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 404

    @patch(
        "app.controllers.user_controller.log_service.get_user_logs",
        new_callable=AsyncMock,
    )
    def test_get_user_logs_success(self, mock_get_user_logs, client, override_auth):
        """Test successful user logs retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_user_logs.return_value = LogListResponse(logs=[])

        response = client.get(
            "/v1/users/507f1f77bcf86cd799439011/logs",
            cookies={"__Host-access_token": "token"},
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


class TestUpdateProfileController:
    """Tests for PUT /users/settings/profile."""

    @patch(
        "app.controllers.user_controller.user_service.update_profile",
        new_callable=AsyncMock,
    )
    def test_update_profile_success(self, mock_update_profile, client, override_auth):
        """Test successful profile update."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_update_profile.return_value = UserResponse(
            id="user123",
            first_name="Jane",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            bio="New bio",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="public",
        )

        response = client.put(
            "/v1/users/settings/profile",
            json={"firstName": "Jane", "bio": "New bio"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "Jane"
        assert data["bio"] == "New bio"
        mock_update_profile.assert_awaited_once()

    def test_update_profile_unauthorized(self, client):
        """Test profile update without authentication."""
        app.dependency_overrides = {}
        response = client.put(
            "/v1/users/settings/profile",
            json={"firstName": "Jane"},
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.update_profile",
        new_callable=AsyncMock,
    )
    def test_update_profile_user_not_found(
        self, mock_update_profile, client, override_auth
    ):
        """Test profile update when user not found."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_update_profile.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.put(
            "/v1/users/settings/profile",
            json={"firstName": "Jane"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 404

    @patch(
        "app.controllers.user_controller.user_service.update_profile",
        new_callable=AsyncMock,
    )
    def test_update_profile_invalid_name(
        self, mock_update_profile, client, override_auth
    ):
        """Test profile update with invalid name characters."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.put(
            "/v1/users/settings/profile",
            json={"firstName": "<script>alert(1)</script>"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 422


class TestChangePasswordController:
    """Tests for PUT /users/settings/password."""

    @patch(
        "app.controllers.user_controller.user_service.change_password",
        new_callable=AsyncMock,
    )
    def test_change_password_success(self, mock_change_password, client, override_auth):
        """Test successful password change."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_change_password.return_value = ChangePasswordResponse(
            message="Password updated successfully"
        )

        response = client.put(
            "/v1/users/settings/password",
            json={"currentPassword": "oldpass123", "newPassword": "newpass123"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.json()["message"] == "Password updated successfully"
        mock_change_password.assert_awaited_once_with(
            user_id="user123",
            current_password="oldpass123",
            new_password="newpass123",
        )

    def test_change_password_unauthorized(self, client):
        """Test password change without authentication."""
        app.dependency_overrides = {}
        response = client.put(
            "/v1/users/settings/password",
            json={"currentPassword": "oldpass123", "newPassword": "newpass123"},
            cookies={"__Host-csrf_token": "test-token"},
            headers={"X-CSRF-Token": "test-token"},
        )
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.change_password",
        new_callable=AsyncMock,
    )
    def test_change_password_invalid_current(
        self, mock_change_password, client, override_auth
    ):
        """Test password change with wrong current password."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_change_password.side_effect = AppException(
            ErrorCodes.INVALID_CURRENT_PASSWORD
        )

        response = client.put(
            "/v1/users/settings/password",
            json={"currentPassword": "wrongpass", "newPassword": "newpass123"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.change_password",
        new_callable=AsyncMock,
    )
    def test_change_password_same_password(
        self, mock_change_password, client, override_auth
    ):
        """Test password change when new password matches current."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_change_password.side_effect = AppException(ErrorCodes.SAME_PASSWORD)

        response = client.put(
            "/v1/users/settings/password",
            json={"currentPassword": "samepass123", "newPassword": "samepass123"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 400


class TestGetPublicProfileController:
    """Tests for GET /users/handle/{handle}."""

    @patch(
        "app.controllers.user_controller.user_service.get_public_profile",
        new_callable=AsyncMock,
    )
    def test_get_public_profile_success(
        self, mock_get_public_profile, client, override_auth
    ):
        """Test successful public profile retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_public_profile.return_value = PublicProfileResponse(
            id="user456",
            first_name="Jane",
            last_name="Doe",
            handle="janedoe",
            bio="A public bio",
            profile_visibility="public",
        )

        response = client.get(
            "/v1/users/handle/janedoe",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["handle"] == "janedoe"
        assert data["profileVisibility"] == "public"
        assert "email" not in data
        assert "password" not in data

    def test_get_public_profile_unauthorized(self, client):
        """Test public profile endpoint without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/users/handle/janedoe")
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.get_public_profile",
        new_callable=AsyncMock,
    )
    def test_get_public_profile_not_found(
        self, mock_get_public_profile, client, override_auth
    ):
        """Test public profile retrieval when handle does not exist."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_public_profile.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get(
            "/v1/users/handle/nonexistent",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 404


class TestGetPublicUserLogsController:
    """Tests for GET /users/handle/{handle}/logs."""

    @patch(
        "app.controllers.user_controller.user_service.get_public_user_logs",
        new_callable=AsyncMock,
    )
    def test_get_public_user_logs_success(
        self, mock_get_public_user_logs, client, override_auth
    ):
        """Test successful public user logs retrieval."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_public_user_logs.return_value = LogListResponse(logs=[])

        response = client.get(
            "/v1/users/handle/janedoe/logs",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []

    def test_get_public_user_logs_unauthorized(self, client):
        """Test public user logs endpoint without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/users/handle/janedoe/logs")
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.get_public_user_logs",
        new_callable=AsyncMock,
    )
    def test_get_public_user_logs_profile_not_public(
        self, mock_get_public_user_logs, client, override_auth
    ):
        """Test public user logs when profile is not public."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_public_user_logs.side_effect = AppException(
            ErrorCodes.PROFILE_NOT_PUBLIC
        )

        response = client.get(
            "/v1/users/handle/janedoe/logs",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 403
