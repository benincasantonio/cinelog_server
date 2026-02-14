"""
E2E tests for authentication endpoints.
Tests the full stack: FastAPI -> AuthService -> Firebase + MongoDB.
"""
from app.utils.error_codes import ErrorCodes


class TestAuthE2E:
    """E2E tests for authentication endpoints."""

    async def test_register_success(self, async_client):
        """Test successful user registration through the full stack."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "e2e_test@example.com",
                "password": "securepassword123",
                "firstName": "E2E",
                "lastName": "Test",
                "handle": "e2etest",
                "dateOfBirth": "1990-01-01"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "e2e_test@example.com"
        assert data["firstName"] == "E2E"
        assert data["lastName"] == "Test"
        assert data["handle"] == "e2etest"
        assert "userId" in data

    async def test_register_duplicate_email(self, async_client):
        """Test registration with duplicate email."""
        payload = {
            "email": "duplicate@example.com",
            "password": "securepassword123",
            "firstName": "First",
            "lastName": "User",
            "handle": "firstuser",
            "dateOfBirth": "1990-01-01"
        }

        # First registration
        await async_client.post("/v1/auth/register", json=payload)

        # Second registration with same email, different handle
        payload["handle"] = "seconduser"
        response = await async_client.post("/v1/auth/register", json=payload)

        assert response.status_code == 409  # EMAIL_ALREADY_EXISTS
        assert response.json()["error_code_name"] == ErrorCodes.EMAIL_ALREADY_EXISTS.error_code_name

    async def test_register_duplicate_handle(self, async_client):
        """Test registration with duplicate handle."""
        # First registration
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "user1@example.com",
                "password": "securepassword123",
                "firstName": "First",
                "lastName": "User",
                "handle": "samehandle",
                "dateOfBirth": "1990-01-01"
            }
        )

        # Second registration with same handle
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "user2@example.com",
                "password": "securepassword123",
                "firstName": "Second",
                "lastName": "User",
                "handle": "samehandle",
                "dateOfBirth": "1990-01-01"
            }
        )

        assert response.status_code == 409  # HANDLE_ALREADY_TAKEN
        assert response.json()["error_code_name"] == ErrorCodes.HANDLE_ALREADY_TAKEN.error_code_name

    async def test_register_invalid_email(self, async_client):
        """Test registration with invalid email format."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepassword123",
                "firstName": "Test",
                "lastName": "User",
                "handle": "testuser",
                "dateOfBirth": "1990-01-01"
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_register_missing_required_fields(self, async_client):
        """Test registration with missing required fields."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "test@example.com"
                # Missing all other required fields
            }
        )

        assert response.status_code == 422  # Validation error
