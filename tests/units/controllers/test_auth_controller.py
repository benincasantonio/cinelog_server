"""
Unit tests for auth controller endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app import app
from app.schemas.auth_schemas import RegisterResponse


@pytest.fixture
def client():
    return TestClient(app)


class TestAuthController:
    """Tests for auth controller endpoints."""

    @patch("app.controllers.auth_controller.auth_service.register")
    def test_register_success(self, mock_register, client):
        """Test successful user registration."""
        mock_register.return_value = RegisterResponse(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            handle="johndoe",
            bio=None,
            user_id="user123",
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
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["firstName"] == "John"
        assert data["handle"] == "johndoe"
        mock_register.assert_called_once()

    @patch("app.controllers.auth_controller.auth_service.register")
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
