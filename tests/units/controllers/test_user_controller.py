import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import date

from app import app
from app.schemas.user_schemas import (
    UserResponse,
    ChangePasswordResponse,
    UserProfileResponse,
)
from app.dependencies.auth_dependency import auth_dependency
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    return lambda: "user123"


class TestUserController:
    @patch(
        "app.controllers.user_controller.user_service.get_user_info",
        new_callable=AsyncMock,
    )
    def test_get_user_info_success(self, mock_get_user_info, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_user_info.return_value = UserResponse(
            id="user123",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            bio="A bio",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="private",
        )

        response = client.get(
            "/v1/users/info", cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "John"
        assert data["profileVisibility"] == "private"
        mock_get_user_info.assert_awaited_once_with("user123")

    def test_get_user_info_unauthorized(self, client):
        app.dependency_overrides = {}
        response = client.get("/v1/users/info")
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.get_user_info",
        new_callable=AsyncMock,
    )
    def test_get_user_info_not_found(self, mock_get_user_info, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_user_info.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get(
            "/v1/users/info", cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 404


class TestGetVisibleProfile:
    @patch(
        "app.controllers.user_controller.user_service.get_visible_profile",
        new_callable=AsyncMock,
    )
    def test_get_visible_profile_success(
        self, mock_get_visible_profile, client, override_auth
    ):
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_visible_profile.return_value = UserProfileResponse(
            first_name="John",
            last_name="Doe",
            handle="johndoe",
            bio="A bio",
            profile_visibility="public",
            date_of_birth=date(1990, 1, 1),
        )

        response = client.get(
            "/v1/users/johndoe/profile",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "John"
        assert data["handle"] == "johndoe"
        assert data["profileVisibility"] == "public"
        mock_get_visible_profile.assert_awaited_once_with(
            handle="johndoe", requester_id="user123"
        )

    def test_get_visible_profile_unauthorized(self, client):
        app.dependency_overrides = {}
        response = client.get("/v1/users/johndoe/profile")
        assert response.status_code == 401

    @patch(
        "app.controllers.user_controller.user_service.get_visible_profile",
        new_callable=AsyncMock,
    )
    def test_get_visible_profile_not_found(
        self, mock_get_visible_profile, client, override_auth
    ):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_visible_profile.side_effect = AppException(ErrorCodes.USER_NOT_FOUND)

        response = client.get(
            "/v1/users/nonexistent/profile",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 404


class TestUpdateProfileController:
    @patch(
        "app.controllers.user_controller.user_service.update_profile",
        new_callable=AsyncMock,
    )
    def test_update_profile_success(self, mock_update_profile, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth

        mock_update_profile.return_value = UserResponse(
            id="user123",
            first_name="Jane",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            bio="New bio",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="private",
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

    @patch(
        "app.controllers.user_controller.user_service.update_profile",
        new_callable=AsyncMock,
    )
    def test_update_profile_with_visibility(
        self, mock_update_profile, client, override_auth
    ):
        app.dependency_overrides[auth_dependency] = override_auth

        mock_update_profile.return_value = UserResponse(
            id="user123",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            bio=None,
            date_of_birth=date(1990, 1, 1),
            profile_visibility="public",
        )

        response = client.put(
            "/v1/users/settings/profile",
            json={"profileVisibility": "public"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["profileVisibility"] == "public"

    def test_update_profile_unauthorized(self, client):
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

    @patch(
        "app.controllers.user_controller.user_service.update_profile",
        new_callable=AsyncMock,
    )
    def test_update_profile_invalid_visibility(
        self, mock_update_profile, client, override_auth
    ):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.put(
            "/v1/users/settings/profile",
            json={"profileVisibility": "hidden"},
            cookies={
                "__Host-access_token": "token",
                "__Host-csrf_token": "test-token",
            },
            headers={"X-CSRF-Token": "test-token"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 422


class TestChangePasswordController:
    @patch(
        "app.controllers.user_controller.user_service.change_password",
        new_callable=AsyncMock,
    )
    def test_change_password_success(self, mock_change_password, client, override_auth):
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
