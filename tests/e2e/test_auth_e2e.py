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

    async def test_login_success(self, async_client):
        """Test successful user login."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "securepassword123",
                "firstName": "Login",
                "lastName": "User",
                "handle": "loginuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        
        response = await async_client.post(
            "/v1/auth/login",
            json={"email": "login@example.com", "password": "securepassword123"}
        )

        assert response.status_code == 200
        assert "__Host-access_token" in response.cookies
        assert "refresh_token" in response.cookies
        assert "__Host-csrf_token" in response.cookies

    async def test_login_invalid_credentials(self, async_client):
        """Test login with wrong password."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "invalid@example.com",
                "password": "securepassword123",
                "firstName": "Inv",
                "lastName": "User",
                "handle": "invuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        
        response = await async_client.post(
            "/v1/auth/login",
            json={"email": "invalid@example.com", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert response.json()["error_code_name"] == ErrorCodes.INVALID_CREDENTIALS.error_code_name

    async def test_logout_success(self, async_client):
        """Test successful logout."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "logout@example.com",
                "password": "securepassword123",
                "firstName": "Logout",
                "lastName": "User",
                "handle": "logoutuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        login_resp = await async_client.post(
            "/v1/auth/login",
            json={"email": "logout@example.com", "password": "securepassword123"}
        )
        csrf_token = login_resp.json()["csrfToken"]
        
        logout_resp = await async_client.post(
            "/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token}
        )
        
        assert logout_resp.status_code == 200
        # In httpx AsyncClient, deleted cookies might be empty or have expired max-age.
        # Check that the Set-Cookie headers for deletion were sent.
        set_cookies = [h[1] for h in logout_resp.headers.multi_items() if h[0].lower() == 'set-cookie']
        assert any("__Host-access_token=" in c and "Max-Age=0" in c for c in set_cookies)
        assert any("refresh_token=" in c and "Max-Age=0" in c for c in set_cookies)

    async def test_refresh_token_success(self, async_client):
        """Test successful token refresh."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "securepassword123",
                "firstName": "Refresh",
                "lastName": "User",
                "handle": "refreshuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        await async_client.post(
            "/v1/auth/login",
            json={"email": "refresh@example.com", "password": "securepassword123"}
        )
        
        refresh_resp = await async_client.post("/v1/auth/refresh")
        
        assert refresh_resp.status_code == 200
        assert "__Host-access_token" in refresh_resp.cookies
        assert "refresh_token" in refresh_resp.cookies
        assert "csrfToken" in refresh_resp.json()

    async def test_refresh_token_invalid(self, async_client):
        """Test refresh token without cookie."""
        refresh_resp = await async_client.post("/v1/auth/refresh")
        assert refresh_resp.status_code == 401

    async def test_forgot_and_reset_password_flow(self, async_client):
        """Test the full forgot and reset password flow."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "reset@example.com",
                "password": "securepassword123",
                "firstName": "Reset",
                "lastName": "User",
                "handle": "resetuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        
        # 1. Forgot password
        forgot_resp = await async_client.post(
            "/v1/auth/forgot-password",
            json={"email": "reset@example.com"}
        )
        assert forgot_resp.status_code == 200
        
        # Fetch the reset code directly from DB since it was mocked via email
        from app.models.user import User
        user = User.objects(email="reset@example.com").first()
        code = user.reset_password_code
        
        # 2. Reset password with valid code
        reset_resp = await async_client.post(
            "/v1/auth/reset-password",
            json={
                "email": "reset@example.com",
                "code": code,
                "newPassword": "newsecurepassword123"
            }
        )
        assert reset_resp.status_code == 200
        
        # 3. Verify old password doesn't work
        login_old = await async_client.post(
            "/v1/auth/login",
            json={"email": "reset@example.com", "password": "securepassword123"}
        )
        assert login_old.status_code == 401
        
        # 4. Verify new password works
        login_new = await async_client.post(
            "/v1/auth/login",
            json={"email": "reset@example.com", "password": "newsecurepassword123"}
        )
        assert login_new.status_code == 200

    async def test_reset_password_invalid_code(self, async_client):
        """Test password reset with invalid code."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "invalidcode@example.com",
                "password": "securepassword123",
                "firstName": "Code",
                "lastName": "User",
                "handle": "codeuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        await async_client.post(
            "/v1/auth/forgot-password",
            json={"email": "invalidcode@example.com"}
        )
        
        reset_resp = await async_client.post(
            "/v1/auth/reset-password",
            json={
                "email": "invalidcode@example.com",
                "code": "WRONG_CODE_XYZ",
                "newPassword": "newsecurepassword123"
            }
        )
        assert reset_resp.status_code == 401

    async def test_csrf_rejection(self, async_client):
        """Test that a mutation route rejects requests without a valid CSRF token."""
        await async_client.post(
            "/v1/auth/register",
            json={
                "email": "csrf@example.com",
                "password": "securepassword123",
                "firstName": "CSRF",
                "lastName": "User",
                "handle": "csrfuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        await async_client.post(
            "/v1/auth/login",
            json={"email": "csrf@example.com", "password": "securepassword123"}
        )
        
        # Try to logout without sending the CSRF header, but with auth cookies present.
        # Since login sets cookies in async_client, the cookies are sent but header is missing.
        logout_resp = await async_client.post("/v1/auth/logout")
        
        # Our CSRFMiddleware should block it
        assert logout_resp.status_code == 403
        assert "CSRF" in logout_resp.text
