"""
E2E tests for authentication endpoints.
Tests the full stack: FastAPI -> AuthService -> Firebase + MongoDB.
"""

from app.utils.error_codes import ErrorCodes
from app.services.token_service import TokenService
from datetime import timedelta


class TestAuthE2E:
    """E2E tests for authentication endpoints."""

    async def test_register_success(self, async_client):
        """Test successful user registration through the full stack."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "e2e_test@example.com",
                "password": "securepassword123",
                "firstName": "End",
                "lastName": "Test",
                "handle": "e2etest",
                "dateOfBirth": "1990-01-01"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "e2e_test@example.com"
        assert data["firstName"] == "End"
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
        """Test refresh token without cookie or invalid."""
        refresh_resp = await async_client.post("/v1/auth/refresh")
        assert refresh_resp.status_code == 401
        
        # Check that the Set-Cookie headers for deletion were sent.
        set_cookies = [h[1] for h in refresh_resp.headers.multi_items() if h[0].lower() == 'set-cookie']
        assert any("__Host-access_token=" in c and "Max-Age=0" in c for c in set_cookies)
        assert any("refresh_token=" in c and "Max-Age=0" in c for c in set_cookies)

    async def test_refresh_token_expired(self, async_client):
        """Test refresh token when it is genuinely expired."""
        # Generate an expired refresh token specifically
        expired_token = TokenService.create_refresh_token(
            data={"sub": "123456789"},
            expires_delta=timedelta(days=-1)  # Expired yesterday
        )
        
        # Set it in the client
        async_client.cookies.set("refresh_token", expired_token)
        
        refresh_resp = await async_client.post("/v1/auth/refresh")
        assert refresh_resp.status_code == 401
        
        # Check that the Set-Cookie headers for deletion were sent.
        set_cookies = [h[1] for h in refresh_resp.headers.multi_items() if h[0].lower() == 'set-cookie']
        assert any("__Host-access_token=" in c and "Max-Age=0" in c for c in set_cookies)
        assert any("refresh_token=" in c and "Max-Age=0" in c for c in set_cookies)

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

    # --- Registration input sanitization: firstName ---

    async def test_register_rejects_script_tag_in_first_name(self, async_client):
        """XSS script tag in firstName must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_fn@example.com",
                "password": "securepassword123",
                "firstName": "<script>alert(1)</script>",
                "lastName": "User",
                "handle": "xssfnuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_img_xss_in_first_name(self, async_client):
        """XSS img onerror in firstName must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_fn2@example.com",
                "password": "securepassword123",
                "firstName": '<img src=x onerror=alert(1)>',
                "lastName": "User",
                "handle": "xssfn2user",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_svg_xss_in_first_name(self, async_client):
        """XSS svg onload in firstName must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_fn3@example.com",
                "password": "securepassword123",
                "firstName": '<svg onload="alert(1)">',
                "lastName": "User",
                "handle": "xssfn3user",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_numbers_in_first_name(self, async_client):
        """Numbers are not allowed in firstName."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "num_fn@example.com",
                "password": "securepassword123",
                "firstName": "John123",
                "lastName": "User",
                "handle": "numfnuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_special_chars_in_first_name(self, async_client):
        """Special characters like @#$ are not allowed in firstName."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "spec_fn@example.com",
                "password": "securepassword123",
                "firstName": "John@#$",
                "lastName": "User",
                "handle": "specfnuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_accepts_hyphenated_first_name(self, async_client):
        """Hyphenated names like Mary-Jane are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "hyph_fn@example.com",
                "password": "securepassword123",
                "firstName": "Mary-Jane",
                "lastName": "Watson",
                "handle": "maryjane",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["firstName"] == "Mary-Jane"

    async def test_register_accepts_apostrophe_in_first_name(self, async_client):
        """Names with apostrophes like O'Brien are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "apos_fn@example.com",
                "password": "securepassword123",
                "firstName": "O'Brien",
                "lastName": "Smith",
                "handle": "obriensmith",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["firstName"] == "O'Brien"

    async def test_register_accepts_accented_first_name(self, async_client):
        """Accented characters like René are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "accent_fn@example.com",
                "password": "securepassword123",
                "firstName": "René",
                "lastName": "Dupont",
                "handle": "renedupont",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["firstName"] == "René"

    # --- Registration input sanitization: lastName ---

    async def test_register_rejects_script_tag_in_last_name(self, async_client):
        """XSS script tag in lastName must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_ln@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "<script>alert(1)</script>",
                "handle": "xsslnuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_iframe_in_last_name(self, async_client):
        """XSS iframe in lastName must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_ln2@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": '<iframe src="http://evil.com">',
                "handle": "xssln2user",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_event_handler_in_last_name(self, async_client):
        """XSS body onload in lastName must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_ln3@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": '<body onload="alert(1)">',
                "handle": "xssln3user",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_numbers_in_last_name(self, async_client):
        """Numbers are not allowed in lastName."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "num_ln@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "Doe123",
                "handle": "numlnuser",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_accepts_hyphenated_last_name(self, async_client):
        """Hyphenated last names like Smith-Jones are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "hyph_ln@example.com",
                "password": "securepassword123",
                "firstName": "Jane",
                "lastName": "Smith-Jones",
                "handle": "smithjones",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["lastName"] == "Smith-Jones"

    async def test_register_accepts_accented_last_name(self, async_client):
        """Accented last names like García are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "accent_ln@example.com",
                "password": "securepassword123",
                "firstName": "Carlos",
                "lastName": "García",
                "handle": "carlosgarcia",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["lastName"] == "García"

    # --- Registration input sanitization: handle ---

    async def test_register_rejects_path_traversal_in_handle(self, async_client):
        """Path traversal payload in handle must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "pt_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "../../../etc/passwd",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_script_tag_in_handle(self, async_client):
        """XSS script tag in handle must be rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "<script>alert(1)</script>",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_spaces_in_handle(self, async_client):
        """Spaces are not allowed in handle."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "space_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "john doe",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_special_chars_in_handle(self, async_client):
        """Special characters like @! are not allowed in handle."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "spec_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "john@doe!",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_hyphen_in_handle(self, async_client):
        """Hyphens are not allowed in handle (only alphanumeric and underscore)."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "hyph_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "john-doe",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_accepts_handle_with_underscores(self, async_client):
        """Underscores are allowed in handle."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "under_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "john_doe",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["handle"] == "john_doe"

    async def test_register_accepts_handle_with_numbers(self, async_client):
        """Numbers are allowed in handle."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "num_handle@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "john123",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["handle"] == "john123"

    # --- Registration input sanitization: bio ---

    async def test_register_strips_script_tag_from_bio(self, async_client):
        """Script tags in bio should be stripped, not rejected."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_bio@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "xssbiouser",
                "bio": "<script>alert(1)</script>",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert "<script>" not in response.json()["bio"]

    async def test_register_strips_img_xss_from_bio(self, async_client):
        """Img onerror XSS in bio should be stripped."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_bio2@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "xssbio2user",
                "bio": '<img src=x onerror=alert(1)>',
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert "<img" not in response.json()["bio"]

    async def test_register_strips_iframe_from_bio(self, async_client):
        """Iframe in bio should be stripped."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "xss_bio3@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "xssbio3user",
                "bio": '<iframe src="http://evil.com"></iframe>',
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert "<iframe" not in response.json()["bio"]

    async def test_register_strips_html_preserves_text_in_bio(self, async_client):
        """HTML tags stripped from bio but text content preserved."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "html_bio@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "htmlbiouser",
                "bio": "I love <b>movies</b> and <i>cinema</i>!",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["bio"] == "I love movies and cinema!"

    async def test_register_preserves_plain_text_bio(self, async_client):
        """Plain text bio passes through unchanged."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "plain_bio@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "plainbiouser",
                "bio": "I love watching movies!",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["bio"] == "I love watching movies!"

    async def test_register_accepts_null_bio(self, async_client):
        """Null bio is accepted."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "null_bio@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "nullbiouser",
                "bio": None,
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        assert response.json()["bio"] is None

    async def test_register_strips_nested_xss_from_bio(self, async_client):
        """Nested XSS tags are stripped from bio."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "nested_bio@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": "nestedbiouser",
                "bio": '<div><script>document.cookie</script></div>',
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        bio = response.json()["bio"]
        assert "<script>" not in bio
        assert "<div>" not in bio

    # --- Combined XSS payloads ---

    async def test_register_bio_sanitized_while_valid_names_accepted(self, async_client):
        """Bio is sanitized (stripped), valid names pass through."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "combo_xss@example.com",
                "password": "securepassword123",
                "firstName": "John",
                "lastName": "Doe",
                "handle": "johndoecombo",
                "bio": 'Hello <script>alert(1)</script> World',
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["firstName"] == "John"
        assert data["lastName"] == "Doe"
        assert "<script>" not in data["bio"]
        assert "Hello" in data["bio"]
        assert "World" in data["bio"]

    async def test_register_rejects_xss_in_first_name_with_valid_others(self, async_client):
        """XSS in firstName is rejected even when other fields are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "combo_fn@example.com",
                "password": "securepassword123",
                "firstName": '<img src=x onerror=alert("xss")>',
                "lastName": "Valid",
                "handle": "combofnuser",
                "bio": "Normal bio",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_xss_in_last_name_with_valid_others(self, async_client):
        """XSS in lastName is rejected even when other fields are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "combo_ln@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": '<svg/onload=alert("xss")>',
                "handle": "combolnuser",
                "bio": "Normal bio",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422

    async def test_register_rejects_xss_in_handle_with_valid_others(self, async_client):
        """XSS in handle is rejected even when other fields are valid."""
        response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "combo_hd@example.com",
                "password": "securepassword123",
                "firstName": "Valid",
                "lastName": "User",
                "handle": '"><script>alert(1)</script>',
                "bio": "Normal bio",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert response.status_code == 422
