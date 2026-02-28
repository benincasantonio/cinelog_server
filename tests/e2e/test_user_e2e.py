"""
E2E tests for user controller endpoints.
Tests the full stack: FastAPI -> UserService -> MongoDB.
"""

from tests.e2e.conftest import register_and_login


class TestUserE2E:
    """E2E tests for user controller endpoints."""

    async def test_get_user_info_success(self, async_client):
        """Test getting user info for authenticated user."""
        user_data = {
            "email": "userinfo_test@example.com",
            "password": "securepassword123",
            "firstName": "UserInfo",
            "lastName": "Test",
            "handle": "userinfotest",
            "dateOfBirth": "1990-01-01",
        }
        login_data = await register_and_login(async_client, user_data)
        user_id = login_data["userId"]

        # Get user info (cookies auto-sent)
        response = await async_client.get("/v1/users/info")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "userinfo_test@example.com"
        assert data["firstName"] == "UserInfo"
        assert data["lastName"] == "Test"
        assert data["handle"] == "userinfotest"
        assert data["id"] == user_id

    async def test_get_user_info_unauthorized(self, async_client):
        """Test getting user info without authentication."""
        response = await async_client.get("/v1/users/info")

        assert response.status_code == 401

    async def test_get_user_info_invalid_token(self, async_client):
        """Test getting user info with invalid token."""
        # Set invalid cookie manually
        async_client.cookies.set("__Host-access_token", "invalid-token")

        response = await async_client.get("/v1/users/info")

        assert response.status_code == 401

    async def test_get_user_logs_empty(self, async_client):
        """Test getting user logs when user has no logs."""
        user_data = {
            "email": "userlogs_test@example.com",
            "password": "securepassword123",
            "firstName": "UserLogs",
            "lastName": "Test",
            "handle": "userlogstest",
            "dateOfBirth": "1990-01-01",
        }
        login_data = await register_and_login(async_client, user_data)
        user_id = login_data["userId"]

        # Get user logs (cookies auto-sent)
        response = await async_client.get(f"/v1/users/{user_id}/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []

    async def test_get_user_logs_unauthorized(self, async_client):
        """Test getting user logs without authentication."""
        response = await async_client.get("/v1/users/some-user-id/logs")

        assert response.status_code == 401

    async def test_get_user_logs_with_data(self, async_client):
        """Test getting user logs when user has logs with movie data."""
        user_data = {
            "email": "userlogs_data@example.com",
            "password": "securepassword123",
            "firstName": "UserLogsData",
            "lastName": "Test",
            "handle": "userlogsdatatest",
            "dateOfBirth": "1990-01-01",
        }
        login_data = await register_and_login(async_client, user_data)
        user_id = login_data["userId"]
        csrf_token = login_data["csrfToken"]

        # Create a log entry (this creates a movie too)
        log_response = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,  # Fight Club
                "dateWatched": "2024-01-15",
                "viewingNotes": "Great movie!",
                "watchedWhere": "cinema",
            },
        )
        assert log_response.status_code == 201

        # Get user logs via user controller endpoint
        response = await async_client.get(f"/v1/users/{user_id}/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1

        log = data["logs"][0]
        assert log["tmdbId"] == 550
        assert log["dateWatched"] == "2024-01-15"
        assert log["viewingNotes"] == "Great movie!"
        assert log["watchedWhere"] == "cinema"

        # Verify movie data is included
        assert "movie" in log
        assert log["movie"]["tmdbId"] == 550
