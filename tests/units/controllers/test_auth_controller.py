"""
Unit tests for auth controller endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from beanie import PydanticObjectId
from unittest.mock import AsyncMock, patch

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.schemas.auth_schemas import RegisterResponse


@pytest.fixture
def client():
    return TestClient(app)


class TestAuthController:
    """Tests for auth controller endpoints."""

    @patch(
        "app.controllers.auth_controller.auth_service.register", new_callable=AsyncMock
    )
    def test_register_success(self, mock_register, client):
        """Test successful user registration."""
        mock_register.return_value = RegisterResponse(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            handle="johndoe",
            bio=None,
            user_id="user123",
            profile_visibility="private",
        )

        response = client.post(
            "/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
                "firstName": "John",
                "lastName": "Doe",
                "handle": "johndoe",
                "dateOfBirth": "1990-01-01",
                "profileVisibility": "private",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["firstName"] == "John"
        assert data["handle"] == "johndoe"
        mock_register.assert_called_once()

    @patch(
        "app.controllers.auth_controller.auth_service.register", new_callable=AsyncMock
    )
    def test_register_with_exception(self, mock_register, client):
        """Test registration that raises AppException."""
        from app.utils.exceptions import AppException
        from app.utils.error_codes import ErrorCodes

        mock_register.side_effect = AppException(ErrorCodes.EMAIL_ALREADY_EXISTS)

        response = client.post(
            "/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
                "firstName": "John",
                "lastName": "Doe",
                "handle": "johndoe",
                "dateOfBirth": "1990-01-01",
                "profileVisibility": "private",
            },
        )

        assert response.status_code == ErrorCodes.EMAIL_ALREADY_EXISTS.error_code

    def test_register_invalid_request(self, client):
        """Test registration with invalid request data."""
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "invalid-email",  # Invalid email format
            },
        )

        assert response.status_code == 422  # Validation error

    @patch(
        "app.controllers.auth_controller.auth_service.forgot_password",
        new_callable=AsyncMock,
    )
    def test_forgot_password_success(self, mock_forgot_password, client):
        """Test successful forgot-password request."""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "message": "If the email exists, a reset code has been sent."
        }
        mock_forgot_password.assert_awaited_once_with("test@example.com")

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_success(self, mock_reset_password, client):
        """Test successful reset-password request."""
        response = client.post(
            "/v1/auth/reset-password",
            json={
                "email": "test@example.com",
                "code": "ABC123",
                "newPassword": "newsecurepassword123",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"message": "Password reset successfully"}
        mock_reset_password.assert_awaited_once_with(
            "test@example.com",
            "ABC123",
            "newsecurepassword123",
        )

    def test_get_csrf_token_success(self, client):
        """Test csrf token endpoint returns a token and sets the cookie."""
        app.dependency_overrides[auth_dependency] = lambda: PydanticObjectId()
        client.cookies.set("__Host-access_token", "token")

        try:
            response = client.get("/v1/auth/csrf")

            assert response.status_code == 200
            assert response.json()["csrfToken"]
            assert response.cookies.get("__Host-csrf_token") is not None
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}

    def test_get_csrf_token_requires_authentication(self, client):
        """Test csrf token endpoint rejects unauthenticated requests."""
        response = client.get("/v1/auth/csrf")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
