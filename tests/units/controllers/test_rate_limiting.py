"""
Unit tests for rate limiting on API endpoints.

Verifies that:
- Rate limit decorators are applied to the correct endpoints
- Requests beyond the limit return 429 with appropriate headers
- Retry-After and X-RateLimit-* headers are present on 429 responses

Note: Redis is swapped for in-memory storage for all unit tests via the
``use_memory_storage_for_rate_limiter`` autouse fixture in conftest.py.
"""

import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from beanie import PydanticObjectId
from datetime import date, datetime

import app.config.rate_limiter as rate_limiter_module
from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.services.auth_rate_limit_service import (
    AuthRateLimitService,
)
from app.services.token_service import TokenService
from app.utils.auth_utils import ACCESS_TOKEN_COOKIE, RATE_LIMIT_SESSION_COOKIE
from app.utils.rate_limit_utils import (
    RATE_LIMIT_SESSION_STATE,
    get_rate_limit_key,
    get_session_rate_limit_key,
)
from app.schemas.auth_schemas import RegisterResponse
from app.schemas.log_schemas import LogCreateResponse
from app.schemas.movie_schemas import MovieResponse
from app.schemas.tmdb_schemas import TMDBMovieSearchResult


RATE_LIMIT_HEADERS = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


def assert_rate_limit_headers(response):
    """Assert that all X-RateLimit-* headers are present on the response."""
    for header in RATE_LIMIT_HEADERS:
        assert header in response.headers, f"Expected {header} header to be present"


def assert_429_response(response):
    """Assert a well-formed 429 rate limit response."""
    assert response.status_code == 429
    assert_rate_limit_headers(response)
    assert "retry-after" in response.headers, (
        "429 response must include Retry-After header"
    )
    body = response.json()
    assert body["error_code_name"] == "RATE_LIMIT_EXCEEDED"
    assert body["error_code"] == 429
    assert body["error_message"] == "Too many requests"
    assert "error_description" in body


def assert_custom_429_response(response):
    """Assert a structured 429 response raised outside slowapi."""
    assert response.status_code == 429
    body = response.json()
    assert body["error_code_name"] == "RATE_LIMIT_EXCEEDED"
    assert body["error_code"] == 429
    assert body["error_message"] == "Too many requests"
    assert "error_description" in body


@pytest.fixture
def client():
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: PydanticObjectId()


@pytest.fixture
def sample_log_response():
    """Minimal LogCreateResponse for rate limit tests."""
    movie = MovieResponse(
        id=PydanticObjectId(),
        title="Fight Club",
        tmdb_id=550,
        poster_path="/path/to/poster.jpg",
        release_date=None,
        overview="A description",
        vote_average=8.5,
        runtime=139,
        original_language="en",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )
    return LogCreateResponse(
        id=str(PydanticObjectId()),
        movie_id=str(PydanticObjectId()),
        movie=movie,
        tmdb_id=550,
        date_watched=date(2024, 1, 15),
        viewing_notes="Great film!",
        poster_path="/path/to/poster.jpg",
        watched_where="cinema",
    )


class TestRateLimitDecoratorsApplied:
    """Verify that rate limit decorators are applied to the correct endpoints."""

    def test_register_has_rate_limit(self):
        key = "app.controllers.auth_controller.register"
        assert key in rate_limiter_module.limiter._route_limits, (
            "register endpoint must have @limiter.limit() decorator"
        )

    def test_login_has_rate_limit(self):
        key = "app.controllers.auth_controller.login"
        assert key in rate_limiter_module.limiter._route_limits, (
            "login endpoint must have @limiter.limit() decorator"
        )

    def test_forgot_password_has_rate_limit(self):
        key = "app.controllers.auth_controller.forgot_password"
        assert key in rate_limiter_module.limiter._route_limits, (
            "forgot_password endpoint must have @limiter.limit() decorator"
        )

    def test_reset_password_has_rate_limit(self):
        key = "app.controllers.auth_controller.reset_password"
        assert key in rate_limiter_module.limiter._route_limits, (
            "reset_password endpoint must have @limiter.limit() decorator"
        )

    def test_get_csrf_token_has_rate_limit(self):
        key = "app.controllers.auth_controller.get_csrf_token"
        assert key in rate_limiter_module.limiter._route_limits, (
            "get_csrf_token endpoint must have @limiter.limit() decorator"
        )

    def test_search_movies_has_rate_limit(self):
        key = "app.controllers.movie_controller.search_movies"
        assert key in rate_limiter_module.limiter._route_limits, (
            "search_movies endpoint must have @limiter.limit() decorator"
        )

    def test_create_log_has_rate_limit(self):
        key = "app.controllers.log_controller.create_log"
        assert key in rate_limiter_module.limiter._route_limits, (
            "create_log endpoint must have @limiter.limit() decorator"
        )

    def test_update_log_has_rate_limit(self):
        key = "app.controllers.log_controller.update_log"
        assert key in rate_limiter_module.limiter._route_limits, (
            "update_log endpoint must have @limiter.limit() decorator"
        )


class TestRegisterRateLimit:
    """Verify POST /v1/auth/register has session and IP limits."""

    REGISTER_PAYLOAD = {
        "email": "test@example.com",
        "password": "securepassword123",
        "firstName": "John",
        "lastName": "Doe",
        "handle": "johndoe",
        "dateOfBirth": "1990-01-01",
        "profileVisibility": "private",
    }

    REGISTER_RESPONSE = RegisterResponse(
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        handle="johndoe",
        bio=None,
        user_id="user123",
        profile_visibility="private",
    )

    @patch(
        "app.controllers.auth_controller.auth_service.register",
        new_callable=AsyncMock,
    )
    def test_register_allows_requests_within_limit(self, mock_register, client):
        """First 5 requests should succeed (201) with rate limit headers."""
        mock_register.return_value = self.REGISTER_RESPONSE

        for _ in range(5):
            response = client.post("/v1/auth/register", json=self.REGISTER_PAYLOAD)
            assert response.status_code == 201
            assert_rate_limit_headers(response)

    @patch(
        "app.controllers.auth_controller.auth_service.register",
        new_callable=AsyncMock,
    )
    def test_register_blocks_request_over_limit(self, mock_register, client):
        """6th request should hit the session-scoped limit."""
        mock_register.return_value = self.REGISTER_RESPONSE

        for _ in range(5):
            client.post("/v1/auth/register", json=self.REGISTER_PAYLOAD)

        response = client.post("/v1/auth/register", json=self.REGISTER_PAYLOAD)
        assert_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.register",
        new_callable=AsyncMock,
    )
    def test_register_session_limit_allows_another_client_on_same_ip(
        self, mock_register
    ):
        """A second client on the same IP should still be allowed before the IP cap."""
        mock_register.return_value = self.REGISTER_RESPONSE

        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        try:
            for _ in range(5):
                response = first_client.post(
                    "/v1/auth/register",
                    json=self.REGISTER_PAYLOAD,
                )
                assert response.status_code == 201

            second_client_response = second_client.post(
                "/v1/auth/register",
                json=self.REGISTER_PAYLOAD,
            )
            assert second_client_response.status_code == 201

            first_client_blocked = first_client.post(
                "/v1/auth/register",
                json=self.REGISTER_PAYLOAD,
            )
            assert_429_response(first_client_blocked)
        finally:
            first_client.close()
            second_client.close()

    @patch(
        "app.controllers.auth_controller.auth_service.register",
        new_callable=AsyncMock,
    )
    def test_register_ip_limit_blocks_after_ten_requests_across_clients(
        self, mock_register
    ):
        """The outer IP gate should block the 11th request across sessions."""
        mock_register.return_value = self.REGISTER_RESPONSE

        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        try:
            for _ in range(5):
                assert (
                    first_client.post(
                        "/v1/auth/register",
                        json=self.REGISTER_PAYLOAD,
                    ).status_code
                    == 201
                )
                assert (
                    second_client.post(
                        "/v1/auth/register",
                        json=self.REGISTER_PAYLOAD,
                    ).status_code
                    == 201
                )

            blocked = first_client.post(
                "/v1/auth/register",
                json=self.REGISTER_PAYLOAD,
            )
            assert_429_response(blocked)
        finally:
            first_client.close()
            second_client.close()


class TestLoginRateLimit:
    """Verify POST /v1/auth/login uses layered rate limits."""

    LOGIN_PAYLOAD = {
        "email": "test@example.com",
        "password": "securepassword123",
    }

    @staticmethod
    def _mock_user():
        return type(
            "User",
            (),
            {
                "id": PydanticObjectId(),
                "email": "test@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "handle": "johndoe",
                "bio": None,
            },
        )()

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_allows_requests_within_limit(self, mock_login, client):
        """First 10 requests should succeed (200) with rate limit headers."""
        mock_login.return_value = self._mock_user()

        for _ in range(10):
            response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
            assert response.status_code == 200
            assert_rate_limit_headers(response)
            client.cookies.pop("__Host-access_token", None)
            client.cookies.pop("refresh_token", None)
            client.cookies.pop("__Host-csrf_token", None)

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_blocks_request_over_limit(self, mock_login, client):
        """11th request should hit the session-scoped login limiter."""
        mock_login.return_value = self._mock_user()

        for _ in range(10):
            client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
            client.cookies.pop("__Host-access_token", None)
            client.cookies.pop("refresh_token", None)
            client.cookies.pop("__Host-csrf_token", None)

        response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
        assert_custom_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_session_limit_allows_another_client_on_same_ip(self, mock_login):
        """Another anonymous client should still be allowed before the outer IP cap."""
        mock_login.return_value = self._mock_user()

        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        try:
            for _ in range(10):
                response = first_client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
                assert response.status_code == 200
                first_client.cookies.pop("__Host-access_token", None)
                first_client.cookies.pop("refresh_token", None)
                first_client.cookies.pop("__Host-csrf_token", None)

            second_client_response = second_client.post(
                "/v1/auth/login",
                json=self.LOGIN_PAYLOAD,
            )
            assert second_client_response.status_code == 200
            second_client.cookies.pop("__Host-access_token", None)
            second_client.cookies.pop("refresh_token", None)
            second_client.cookies.pop("__Host-csrf_token", None)

            first_client_blocked = first_client.post(
                "/v1/auth/login",
                json=self.LOGIN_PAYLOAD,
            )
            assert_custom_429_response(first_client_blocked)
        finally:
            first_client.close()
            second_client.close()

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_ip_limit_blocks_after_thirty_requests_across_clients(
        self, mock_login
    ):
        """The outer IP gate should block the 31st request across sessions."""
        mock_login.return_value = self._mock_user()

        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        third_client = TestClient(app, base_url="https://testserver")
        try:
            for _ in range(10):
                assert (
                    first_client.post(
                        "/v1/auth/login", json=self.LOGIN_PAYLOAD
                    ).status_code
                    == 200
                )
                first_client.cookies.pop("__Host-access_token", None)
                first_client.cookies.pop("refresh_token", None)
                first_client.cookies.pop("__Host-csrf_token", None)
                assert (
                    second_client.post(
                        "/v1/auth/login",
                        json=self.LOGIN_PAYLOAD,
                    ).status_code
                    == 200
                )
                second_client.cookies.pop("__Host-access_token", None)
                second_client.cookies.pop("refresh_token", None)
                second_client.cookies.pop("__Host-csrf_token", None)
                assert (
                    third_client.post(
                        "/v1/auth/login",
                        json=self.LOGIN_PAYLOAD,
                    ).status_code
                    == 200
                )
                third_client.cookies.pop("__Host-access_token", None)
                third_client.cookies.pop("refresh_token", None)
                third_client.cookies.pop("__Host-csrf_token", None)

            blocked = first_client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
            assert_429_response(blocked)
        finally:
            first_client.close()
            second_client.close()
            third_client.close()

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_failed_account_limit_blocks_after_five_invalid_attempts(
        self, mock_login, client
    ):
        """The email-based account bucket should block the 6th login attempt."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        mock_login.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)

        for _ in range(5):
            response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
            assert response.status_code == 401

        response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
        assert_custom_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_failed_account_limit_short_circuits_before_auth_service(
        self, mock_login, client
    ):
        """Once exhausted, the account limiter should block before auth_service.login runs."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        mock_login.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)

        for _ in range(5):
            response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)
            assert response.status_code == 401

        call_count_before_block = mock_login.await_count
        response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)

        assert_custom_429_response(response)
        assert mock_login.await_count == call_count_before_block

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_success_clears_the_failure_bucket(self, mock_login, client):
        """Successful login should clear the email-hash failure bucket."""

        mock_login.return_value = self._mock_user()

        with patch.object(AuthRateLimitService, "_clear_limit") as clear_limit:
            response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)

        assert response.status_code == 200
        clear_limit.assert_called_once()

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_ignores_failure_bucket_cleanup_errors(self, mock_login, client):
        """Successful login should not fail if failure-bucket cleanup raises."""

        mock_login.return_value = self._mock_user()

        with (
            patch.object(
                AuthRateLimitService,
                "clear_login_failures",
                side_effect=RuntimeError("redis down"),
            ),
            patch("app.controllers.auth_controller.logger.warning") as mock_warning,
        ):
            response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)

        assert response.status_code == 200
        mock_warning.assert_called_once()

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_does_not_require_rate_limit_cache_dependency(
        self, mock_login, client
    ):
        """Login account limiting should not depend on a request-state cache helper."""
        mock_login.return_value = self._mock_user()

        response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)

        assert response.status_code == 200

    @patch(
        "app.controllers.auth_controller.auth_service.login",
        new_callable=AsyncMock,
    )
    def test_login_failure_bucket_hashes_unknown_email(self, mock_login, client):
        """Failed login attempts should use the same hashed email identifier."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        original_hit_limit = AuthRateLimitService._hit_limit
        mock_login.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)
        captured: dict[str, str] = {}

        def record_hit_limit(self, limit_item, scope: str, key: str) -> bool:
            if scope == "auth:login:account":
                captured["scope"] = scope
                captured["key"] = key
            return original_hit_limit(self, limit_item, scope, key)

        with patch.object(
            AuthRateLimitService,
            "_hit_limit",
            new=record_hit_limit,
        ):
            response = client.post("/v1/auth/login", json=self.LOGIN_PAYLOAD)

        assert response.status_code == 401
        assert captured["scope"] == "auth:login:account"
        assert captured["key"].startswith("identifier:")
        assert "test@example.com" not in captured["key"]


class TestForgotPasswordRateLimit:
    """Verify POST /v1/auth/forgot-password uses layered rate limits."""

    FORGOT_PASSWORD_PAYLOAD = {"email": "test@example.com"}

    @patch(
        "app.controllers.auth_controller.auth_service.forgot_password",
        new_callable=AsyncMock,
    )
    def test_forgot_password_allows_requests_within_limit(
        self, mock_forgot_password, client
    ):
        """First 3 requests should succeed (200) with rate limit headers."""
        mock_forgot_password.return_value = None

        for _ in range(3):
            response = client.post(
                "/v1/auth/forgot-password",
                json=self.FORGOT_PASSWORD_PAYLOAD,
            )
            assert response.status_code == 200
            assert_rate_limit_headers(response)

    @patch(
        "app.controllers.auth_controller.auth_service.forgot_password",
        new_callable=AsyncMock,
    )
    def test_forgot_password_blocks_request_over_limit(
        self, mock_forgot_password, client
    ):
        """4th request should hit the session/account forgot-password limit."""
        mock_forgot_password.return_value = None

        for _ in range(3):
            client.post(
                "/v1/auth/forgot-password",
                json=self.FORGOT_PASSWORD_PAYLOAD,
            )

        response = client.post(
            "/v1/auth/forgot-password",
            json=self.FORGOT_PASSWORD_PAYLOAD,
        )
        assert_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.forgot_password",
        new_callable=AsyncMock,
    )
    def test_forgot_password_account_limit_blocks_across_clients(
        self, mock_forgot_password
    ):
        """The hashed-email account bucket should block the 6th cross-client attempt."""
        mock_forgot_password.return_value = None

        clients = [
            TestClient(
                app, base_url="https://testserver", client=(f"10.0.2.{i}", 50000)
            )
            for i in range(1, 7)
        ]
        try:
            for client in clients[:5]:
                response = client.post(
                    "/v1/auth/forgot-password",
                    json=self.FORGOT_PASSWORD_PAYLOAD,
                )
                assert response.status_code == 200

            blocked_response = clients[5].post(
                "/v1/auth/forgot-password",
                json=self.FORGOT_PASSWORD_PAYLOAD,
            )
            assert_custom_429_response(blocked_response)
        finally:
            for client in clients:
                client.close()

    @patch(
        "app.controllers.auth_controller.auth_service.forgot_password",
        new_callable=AsyncMock,
    )
    def test_forgot_password_ip_limit_blocks_after_six_requests_across_clients(
        self, mock_forgot_password
    ):
        """The outer IP gate should block after the broader IP window is exhausted."""
        mock_forgot_password.return_value = None

        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        third_client = TestClient(app, base_url="https://testserver")
        try:
            assert (
                first_client.post(
                    "/v1/auth/forgot-password",
                    json={"email": "other1@example.com"},
                ).status_code
                == 200
            )
            assert (
                second_client.post(
                    "/v1/auth/forgot-password",
                    json={"email": "other2@example.com"},
                ).status_code
                == 200
            )
            assert (
                third_client.post(
                    "/v1/auth/forgot-password",
                    json={"email": "other3@example.com"},
                ).status_code
                == 200
            )
            assert (
                first_client.post(
                    "/v1/auth/forgot-password",
                    json={"email": "other4@example.com"},
                ).status_code
                == 200
            )
            assert (
                second_client.post(
                    "/v1/auth/forgot-password",
                    json={"email": "other5@example.com"},
                ).status_code
                == 200
            )
            assert (
                third_client.post(
                    "/v1/auth/forgot-password",
                    json={"email": "other6@example.com"},
                ).status_code
                == 200
            )

            blocked = first_client.post(
                "/v1/auth/forgot-password",
                json={"email": "other7@example.com"},
            )
            assert_429_response(blocked)
        finally:
            first_client.close()
            second_client.close()
            third_client.close()


class TestResetPasswordRateLimit:
    """Verify POST /v1/auth/reset-password uses layered rate limits."""

    RESET_PASSWORD_PAYLOAD = {
        "email": "test@example.com",
        "code": "ABC123",
        "newPassword": "newsecurepassword123",
    }

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_allows_requests_within_limit(
        self, mock_reset_password, client
    ):
        """First 5 requests should succeed (200) with rate limit headers."""
        mock_reset_password.return_value = True

        for _ in range(5):
            response = client.post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )
            assert response.status_code == 200
            assert_rate_limit_headers(response)

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_blocks_request_over_limit(
        self, mock_reset_password, client
    ):
        """11th request should hit the session/account reset-password limit."""
        mock_reset_password.return_value = True

        for _ in range(10):
            client.post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )

        response = client.post(
            "/v1/auth/reset-password",
            json=self.RESET_PASSWORD_PAYLOAD,
        )
        assert_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_invalid_code_limit_blocks_on_eleventh_failure(
        self, mock_reset_password, client
    ):
        """The 11th invalid reset attempt should hit the reset account bucket."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        mock_reset_password.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)

        for _ in range(10):
            response = client.post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )
            assert response.status_code == 401

        response = client.post(
            "/v1/auth/reset-password",
            json=self.RESET_PASSWORD_PAYLOAD,
        )
        assert_custom_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_account_limit_blocks_on_eleventh_failure_across_clients(
        self, mock_reset_password
    ):
        """The reset-password account bucket should block the 11th invalid attempt across clients."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        mock_reset_password.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)

        clients = [
            TestClient(
                app, base_url="https://testserver", client=(f"10.0.0.{i}", 50000)
            )
            for i in range(1, 12)
        ]

        try:
            for client in clients[:10]:
                response = client.post(
                    "/v1/auth/reset-password",
                    json=self.RESET_PASSWORD_PAYLOAD,
                )
                assert response.status_code == 401

            response = clients[10].post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )
            assert_custom_429_response(response)
        finally:
            for client in clients:
                client.close()

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_account_limit_short_circuits_before_reset_logic(
        self, mock_reset_password
    ):
        """Once the reset-password account bucket is exhausted, reset logic should not run."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        mock_reset_password.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)

        clients = [
            TestClient(
                app, base_url="https://testserver", client=(f"10.0.1.{i}", 50000)
            )
            for i in range(1, 12)
        ]

        try:
            for client in clients[:10]:
                response = client.post(
                    "/v1/auth/reset-password",
                    json=self.RESET_PASSWORD_PAYLOAD,
                )
                assert response.status_code == 401

            call_count_before_block = mock_reset_password.await_count
            response = clients[10].post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )

            assert_custom_429_response(response)
            assert mock_reset_password.await_count == call_count_before_block
        finally:
            for client in clients:
                client.close()

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_session_limit_blocks_before_account_limit(
        self, mock_reset_password, client
    ):
        """A single client should hit the session limit before the account bucket is exhausted."""
        mock_reset_password.return_value = True

        for _ in range(10):
            response = client.post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )
            assert response.status_code == 200

        response = client.post(
            "/v1/auth/reset-password",
            json=self.RESET_PASSWORD_PAYLOAD,
        )
        assert_429_response(response)

    @patch(
        "app.controllers.auth_controller.auth_service.reset_password",
        new_callable=AsyncMock,
    )
    def test_reset_password_invalid_code_limit_short_circuits_on_eleventh_failure(
        self, mock_reset_password, client
    ):
        """Once exhausted, the reset account bucket should block before reset logic runs."""
        from app.utils.error_codes import ErrorCodes
        from app.utils.exceptions import AppException

        mock_reset_password.side_effect = AppException(ErrorCodes.INVALID_CREDENTIALS)

        for _ in range(10):
            response = client.post(
                "/v1/auth/reset-password",
                json=self.RESET_PASSWORD_PAYLOAD,
            )
            assert response.status_code == 401

        call_count_before_block = mock_reset_password.await_count
        response = client.post(
            "/v1/auth/reset-password",
            json=self.RESET_PASSWORD_PAYLOAD,
        )

        assert_custom_429_response(response)
        assert mock_reset_password.await_count == call_count_before_block


class TestCsrfRateLimit:
    """Verify GET /v1/auth/csrf is authenticated and rate limited."""

    def test_get_csrf_token_requires_authentication(self, client):
        """Unauthenticated requests should be rejected before rate limiting matters."""
        response = client.get("/v1/auth/csrf")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

    def test_get_csrf_token_allows_requests_within_limit(self, client, override_auth):
        """First 300 authenticated requests should succeed (200)."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")

        try:
            for _ in range(300):
                response = client.get("/v1/auth/csrf")
                assert response.status_code == 200
                assert_rate_limit_headers(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}

    def test_get_csrf_token_blocks_request_over_limit(self, client, override_auth):
        """301st authenticated request should be rate-limited (429)."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")

        try:
            for _ in range(300):
                client.get("/v1/auth/csrf")

            response = client.get("/v1/auth/csrf")
            assert_429_response(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}


class TestSearchMoviesRateLimit:
    """Verify GET /v1/movies/search is limited to 20 requests per minute."""

    @pytest.fixture
    def user_one_token(self):
        return TokenService.create_access_token({"sub": "507f1f77bcf86cd799439011"})

    @pytest.fixture
    def user_two_token(self):
        return TokenService.create_access_token({"sub": "507f1f77bcf86cd799439012"})

    @patch(
        "app.controllers.movie_controller.tmdb_service.search_movie",
        new_callable=AsyncMock,
    )
    def test_search_movies_user_limit_is_scoped_to_authenticated_user(
        self, mock_search, user_one_token, user_two_token
    ):
        """A second user on the same IP should get a fresh bucket."""
        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        mock_search.return_value = TMDBMovieSearchResult(
            page=1, total_results=0, total_pages=0, results=[]
        )

        try:
            first_client.cookies.set("__Host-access_token", user_one_token)
            second_client.cookies.set("__Host-access_token", user_two_token)

            for _ in range(20):
                response = first_client.get("/v1/movies/search?query=test")
                assert response.status_code == 200

            blocked = first_client.get("/v1/movies/search?query=test")
            assert_429_response(blocked)

            allowed = second_client.get("/v1/movies/search?query=test")
            assert allowed.status_code == 200
        finally:
            first_client.close()
            second_client.close()

    @patch(
        "app.controllers.movie_controller.tmdb_service.search_movie",
        new_callable=AsyncMock,
    )
    def test_search_movies_same_user_shares_limit_across_clients(
        self, mock_search, user_one_token
    ):
        """Two clients for the same authenticated user should share one bucket."""
        first_client = TestClient(app, base_url="https://testserver")
        second_client = TestClient(app, base_url="https://testserver")
        mock_search.return_value = TMDBMovieSearchResult(
            page=1, total_results=0, total_pages=0, results=[]
        )

        try:
            first_client.cookies.set("__Host-access_token", user_one_token)
            second_client.cookies.set("__Host-access_token", user_one_token)

            for _ in range(20):
                response = first_client.get("/v1/movies/search?query=test")
                assert response.status_code == 200

            blocked = second_client.get("/v1/movies/search?query=test")
            assert_429_response(blocked)
        finally:
            first_client.close()
            second_client.close()

    @patch(
        "app.controllers.movie_controller.tmdb_service.search_movie",
        new_callable=AsyncMock,
    )
    def test_search_movies_allows_requests_within_limit(
        self, mock_search, client, override_auth
    ):
        """First 20 requests should succeed (200) with rate limit headers."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")
        mock_search.return_value = TMDBMovieSearchResult(
            page=1, total_results=0, total_pages=0, results=[]
        )

        try:
            for _ in range(20):
                response = client.get("/v1/movies/search?query=test")
                assert response.status_code == 200
                assert_rate_limit_headers(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}

    @patch(
        "app.controllers.movie_controller.tmdb_service.search_movie",
        new_callable=AsyncMock,
    )
    def test_search_movies_blocks_request_over_limit(
        self, mock_search, client, override_auth
    ):
        """21st request should be rate-limited (429) with proper headers and body."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")
        mock_search.return_value = TMDBMovieSearchResult(
            page=1, total_results=0, total_pages=0, results=[]
        )

        try:
            for _ in range(20):
                client.get("/v1/movies/search?query=test")

            response = client.get("/v1/movies/search?query=test")
            assert_429_response(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}


class TestCreateLogRateLimit:
    """Verify POST /v1/logs/ is limited to 20 requests per minute."""

    LOG_PAYLOAD = {
        "movieId": "507f1f77bcf86cd799439011",
        "tmdbId": 550,
        "dateWatched": "2024-01-15",
        "viewingNotes": "Great film!",
        "posterPath": "/path/to/poster.jpg",
        "watchedWhere": "cinema",
    }

    @patch(
        "app.controllers.log_controller.log_service.create_log",
        new_callable=AsyncMock,
    )
    def test_create_log_allows_requests_within_limit(
        self, mock_create_log, client, override_auth, sample_log_response
    ):
        """First 20 requests should succeed (201) with rate limit headers."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")
        client.cookies.set("__Host-csrf_token", "test-token")
        mock_create_log.return_value = sample_log_response

        try:
            for _ in range(20):
                response = client.post(
                    "/v1/logs/",
                    json=self.LOG_PAYLOAD,
                    headers={"X-CSRF-Token": "test-token"},
                )
                assert response.status_code == 201
                assert_rate_limit_headers(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}

    @patch(
        "app.controllers.log_controller.log_service.create_log",
        new_callable=AsyncMock,
    )
    def test_create_log_blocks_request_over_limit(
        self, mock_create_log, client, override_auth, sample_log_response
    ):
        """21st request should be rate-limited (429) with proper headers and body."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")
        client.cookies.set("__Host-csrf_token", "test-token")
        mock_create_log.return_value = sample_log_response

        try:
            for _ in range(20):
                client.post(
                    "/v1/logs/",
                    json=self.LOG_PAYLOAD,
                    headers={"X-CSRF-Token": "test-token"},
                )

            response = client.post(
                "/v1/logs/",
                json=self.LOG_PAYLOAD,
                headers={"X-CSRF-Token": "test-token"},
            )
            assert_429_response(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}


class TestUpdateLogRateLimit:
    """Verify PUT /v1/logs/{log_id} is limited to 10 requests per minute."""

    LOG_UPDATE_PAYLOAD = {
        "viewingNotes": "Updated notes",
        "watchedWhere": "streaming",
    }

    @patch(
        "app.controllers.log_controller.log_service.update_log",
        new_callable=AsyncMock,
    )
    def test_update_log_allows_requests_within_limit(
        self, mock_update_log, client, override_auth, sample_log_response
    ):
        """First 10 requests should succeed (200) with rate limit headers."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")
        client.cookies.set("__Host-csrf_token", "test-token")
        mock_update_log.return_value = sample_log_response

        try:
            for _ in range(10):
                response = client.put(
                    "/v1/logs/log123",
                    json=self.LOG_UPDATE_PAYLOAD,
                    headers={"X-CSRF-Token": "test-token"},
                )
                assert response.status_code == 200
                assert_rate_limit_headers(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}

    @patch(
        "app.controllers.log_controller.log_service.update_log",
        new_callable=AsyncMock,
    )
    def test_update_log_blocks_request_over_limit(
        self, mock_update_log, client, override_auth, sample_log_response
    ):
        """11th request should be rate-limited (429) with proper headers and body."""
        app.dependency_overrides[auth_dependency] = override_auth
        client.cookies.set("__Host-access_token", "token")
        client.cookies.set("__Host-csrf_token", "test-token")
        mock_update_log.return_value = sample_log_response

        try:
            for _ in range(10):
                client.put(
                    "/v1/logs/log123",
                    json=self.LOG_UPDATE_PAYLOAD,
                    headers={"X-CSRF-Token": "test-token"},
                )

            response = client.put(
                "/v1/logs/log123",
                json=self.LOG_UPDATE_PAYLOAD,
                headers={"X-CSRF-Token": "test-token"},
            )
            assert_429_response(response)
        finally:
            client.cookies.clear()
            app.dependency_overrides = {}


class TestGetRateLimitKey:
    """Verify get_rate_limit_key returns the authenticated-or-IP key."""

    def _make_request(
        self,
        user_id: str | None = None,
        validated_session_id: str | None = None,
        session_cookie: str | None = None,
        remote_addr: str = "127.0.0.1",
    ) -> SimpleNamespace:
        request = SimpleNamespace()
        request.state = SimpleNamespace()
        if user_id is not None:
            request.state.user_id = user_id
        if validated_session_id is not None:
            setattr(request.state, RATE_LIMIT_SESSION_STATE, validated_session_id)

        cookies: dict[str, str] = {}
        if session_cookie is not None:
            cookies[RATE_LIMIT_SESSION_COOKIE] = session_cookie
        request.cookies = cookies
        request.client = SimpleNamespace(host=remote_addr)

        return request

    def test_returns_user_key_when_authenticated(self):
        request = self._make_request(user_id="abc123")
        assert get_rate_limit_key(request) == "user:abc123"

    def test_returns_ip_key_when_validated_session_present(self):
        request = self._make_request(validated_session_id="sess456")
        assert get_rate_limit_key(request) == "ip:127.0.0.1"

    def test_returns_ip_key_when_only_raw_session_cookie_present(self):
        request = self._make_request(session_cookie="sess456")
        assert get_rate_limit_key(request) == "ip:127.0.0.1"

    def test_returns_ip_key_as_fallback(self):
        request = self._make_request(remote_addr="192.168.1.1")
        assert get_rate_limit_key(request) == "ip:192.168.1.1"

    def test_user_id_takes_priority_over_validated_session(self):
        request = self._make_request(
            user_id="abc123",
            validated_session_id="sess456",
            session_cookie="sess456",
        )
        assert get_rate_limit_key(request) == "user:abc123"


class TestGetSessionRateLimitKey:
    """Verify get_session_rate_limit_key uses the validated anonymous session."""

    def _make_request(
        self,
        validated_session_id: str | None = None,
        session_cookie: str | None = None,
        remote_addr: str = "127.0.0.1",
    ) -> SimpleNamespace:
        request = SimpleNamespace()
        request.state = SimpleNamespace()
        if validated_session_id is not None:
            setattr(request.state, RATE_LIMIT_SESSION_STATE, validated_session_id)

        cookies: dict[str, str] = {}
        if session_cookie is not None:
            cookies[RATE_LIMIT_SESSION_COOKIE] = session_cookie
        request.cookies = cookies
        request.client = SimpleNamespace(host=remote_addr)

        return request

    def test_returns_session_key_when_validated_session_present(self):
        request = self._make_request(validated_session_id="sess456")
        assert get_session_rate_limit_key(request) == "session:sess456"

    def test_returns_ip_key_when_only_raw_session_cookie_present(self):
        request = self._make_request(session_cookie="sess456")
        assert get_session_rate_limit_key(request) == "ip:127.0.0.1"

    def test_returns_ip_key_as_fallback(self):
        request = self._make_request(remote_addr="192.168.1.1")
        assert get_session_rate_limit_key(request) == "ip:192.168.1.1"


class TestRateLimitSessionMiddleware:
    """Verify RateLimitSessionMiddleware only manages session-tracked auth routes."""

    def test_sets_session_cookie_for_missing_session_on_tracked_route(
        self, client, fake_cache_client, rate_limit_cache_service
    ):
        """Should issue and register a new session on a session-tracked auth route."""
        with patch(
            "app.controllers.auth_controller.auth_service.forgot_password",
            new_callable=AsyncMock,
        ) as mock_forgot_password:
            mock_forgot_password.return_value = None
            response = client.post(
                "/v1/auth/forgot-password",
                json={"email": "test@example.com"},
            )
        session_cookie = response.cookies.get(RATE_LIMIT_SESSION_COOKIE)
        assert session_cookie is not None, (
            "Expected session cookie to be set for a session-tracked route"
        )
        assert (
            rate_limit_cache_service.build_session_key(session_cookie)
            in fake_cache_client.values
        )

    def test_does_not_set_cookie_for_untracked_route(self, client, fake_cache_client):
        """Routes outside the session-tracked auth list should not issue a session."""
        response = client.get("/")
        assert RATE_LIMIT_SESSION_COOKIE not in response.cookies, (
            "Should not set session cookie for an untracked route"
        )
        assert fake_cache_client.set_calls == []

    def test_access_token_cookie_does_not_skip_tracking_on_public_auth_route(
        self, client, fake_cache_client
    ):
        """A raw access-token cookie must not bypass tracking on public auth routes."""
        client.cookies.set(ACCESS_TOKEN_COOKIE, "some-token")
        with patch(
            "app.controllers.auth_controller.auth_service.forgot_password",
            new_callable=AsyncMock,
        ) as mock_forgot_password:
            mock_forgot_password.return_value = None
            response = client.post(
                "/v1/auth/forgot-password",
                json={"email": "test@example.com"},
            )
        session_cookie = response.cookies.get(RATE_LIMIT_SESSION_COOKIE)
        assert session_cookie is not None, (
            "Expected session cookie to still be issued on a session-tracked route"
        )
        assert fake_cache_client.set_calls != []
        client.cookies.clear()

    def test_does_not_reset_cookie_when_session_is_valid(
        self, client, fake_cache_client, rate_limit_cache_service
    ):
        """Should trust a session cookie only when it exists in Redis."""
        session_id = "existing-session"
        session_key = rate_limit_cache_service.build_session_key(session_id)
        fake_cache_client.values[session_key] = '{"active": true}'
        client.cookies.set(RATE_LIMIT_SESSION_COOKIE, session_id)

        with patch(
            "app.controllers.auth_controller.auth_service.forgot_password",
            new_callable=AsyncMock,
        ) as mock_forgot_password:
            mock_forgot_password.return_value = None
            response = client.post(
                "/v1/auth/forgot-password",
                json={"email": "test@example.com"},
            )

        assert RATE_LIMIT_SESSION_COOKIE not in response.cookies, (
            "Should not re-set session cookie when the current one is valid"
        )
        assert fake_cache_client.set_calls[-1] == (
            session_key,
            '{"active": true}',
            604800,
        )
        client.cookies.clear()

    def test_reissues_cookie_when_session_cookie_is_unknown(
        self, client, fake_cache_client, rate_limit_cache_service
    ):
        """Should replace a client-provided session that is not registered in Redis."""
        client.cookies.set(RATE_LIMIT_SESSION_COOKIE, "unknown-session")
        with patch(
            "app.controllers.auth_controller.auth_service.forgot_password",
            new_callable=AsyncMock,
        ) as mock_forgot_password:
            mock_forgot_password.return_value = None
            response = client.post(
                "/v1/auth/forgot-password",
                json={"email": "test@example.com"},
            )

        new_session_id = response.cookies.get(RATE_LIMIT_SESSION_COOKIE)
        assert new_session_id is not None
        assert new_session_id != "unknown-session"
        assert (
            rate_limit_cache_service.build_session_key(new_session_id)
            in fake_cache_client.values
        )
        client.cookies.clear()
