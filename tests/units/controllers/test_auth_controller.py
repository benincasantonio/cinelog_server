"""
Unit tests for auth controller endpoints.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_auth_service
from app.schemas.auth_schemas import RegisterResponse


@pytest.fixture
def client():
    return TestClient(app)


class TestAuthController:
    """Tests for auth controller endpoints."""

    @patch.object(get_auth_service(), "send_registration_verification_code", new_callable=AsyncMock)
    def test_send_register_verification_code_success(self, mock_send_code, client):
        """Test successful registration verification code request."""
        response = client.post(
            "/v1/auth/register/send-code",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 200
        assert response.json() == {"message": "If the email can be registered, a verification code has been sent."}
        mock_send_code.assert_awaited_once_with("test@example.com")

    @patch.object(get_auth_service(), "send_registration_verification_code", new_callable=AsyncMock)
    def test_send_register_verification_code_with_exception(self, mock_send_code, client):
        """Test registration verification code request that raises AppException."""
        from app.utils.error_codes_utils import ErrorCodes
        from app.utils.exceptions_utils import AppException

        mock_send_code.side_effect = AppException(ErrorCodes.RATE_LIMIT_EXCEEDED)

        response = client.post(
            "/v1/auth/register/send-code",
            json={"email": "test@example.com"},
        )

        assert response.status_code == ErrorCodes.RATE_LIMIT_EXCEEDED.error_code

    @patch.object(get_auth_service(), "register", new_callable=AsyncMock)
    def test_register_success(self, mock_register, client):
        """Test successful user registration."""
        mock_register.return_value = RegisterResponse(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            handle="johndoe",
            bio=None,
            user_id="user123",
            profile_visibility="followers_only",
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
                "profileVisibility": " FOLLOWERS_ONLY ",
                "verificationCode": "ABC123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["firstName"] == "John"
        assert data["handle"] == "johndoe"
        assert data["profileVisibility"] == "followers_only"
        request = mock_register.await_args.kwargs["request"]
        assert request.profile_visibility == "followers_only"

    @patch.object(get_auth_service(), "register", new_callable=AsyncMock)
    def test_register_with_exception(self, mock_register, client):
        """Test registration that raises AppException."""
        from app.utils.error_codes_utils import ErrorCodes
        from app.utils.exceptions_utils import AppException

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
                "verificationCode": "ABC123",
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

    def test_register_validation_error_does_not_echo_password(self, client):
        """Validation errors must not leak the submitted password (issue #24)."""
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SuperSecret1!",
                "handle": "validhandle",
                "firstName": "Tony",
                "lastName": "B",
            },
        )

        assert response.status_code == 422
        assert "SuperSecret1!" not in response.text
        details = response.json()["detail"]
        assert all("input" not in error for error in details)
        assert all("loc" in error and "msg" in error for error in details)

    def test_login_validation_error_does_not_echo_password(self, client):
        """Missing-field errors must not echo the payload containing the password."""
        response = client.post(
            "/v1/auth/login",
            json={"password": "SuperSecret1!"},  # email missing
        )

        assert response.status_code == 422
        assert "SuperSecret1!" not in response.text
        assert all("input" not in error for error in response.json()["detail"])

    def test_reset_password_validation_error_does_not_echo_secrets(self, client):
        """Field-level errors must not echo the new password or reset code."""
        response = client.post(
            "/v1/auth/reset-password",
            json={
                "email": "test@example.com",
                "code": "reset-code-123",
                "newPassword": "Pw1!",  # violates min_length=8
            },
        )

        assert response.status_code == 422
        assert "Pw1!" not in response.text
        assert "reset-code-123" not in response.text
        assert all("input" not in error for error in response.json()["detail"])

    @patch.object(get_auth_service(), "forgot_password", new_callable=AsyncMock)
    def test_forgot_password_success(self, mock_forgot_password, client):
        """Test successful forgot-password request."""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 200
        assert response.json() == {"message": "If the email exists, a reset code has been sent."}
        mock_forgot_password.assert_awaited_once_with("test@example.com")

    @patch.object(get_auth_service(), "reset_password", new_callable=AsyncMock)
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
        app.dependency_overrides[auth_dependency] = lambda: uuid4()
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
