"""
E2E tests for log controller endpoints.
Tests the full stack: FastAPI -> LogService -> MongoDB.
"""
from tests.e2e.conftest import register_and_login


class TestLogE2E:
    """E2E tests for log controller endpoints."""

    async def test_create_log_success(self, async_client):
        """Test creating a new log entry."""
        user_data = {
            "email": "createlog_test@example.com",
            "password": "securepassword123",
            "firstName": "CreateLog",
            "lastName": "Test",
            "handle": "createlogtest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        # Create a log entry (using a real TMDB ID for a movie)
        response = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,  # Fight Club
                "dateWatched": "2024-01-15",
                "viewingNotes": "Great movie!",
                "watchedWhere": "cinema"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tmdbId"] == 550
        assert data["dateWatched"] == "2024-01-15"
        assert data["viewingNotes"] == "Great movie!"
        assert data["watchedWhere"] == "cinema"
        assert "id" in data
        assert "movieId" in data
        # Verify movie was created
        assert "movie" in data
        assert data["movie"]["tmdbId"] == 550

    async def test_create_log_unauthorized(self, async_client):
        """Test creating a log without authentication."""
        # No login -> No cookies
        response = await async_client.post(
            "/v1/logs/",
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15"
            }
        )
        # Should be 401 (Unauthorized) OR 403 (CSRF missing)
        assert response.status_code in [401, 403]

    async def test_get_logs_success(self, async_client):
        """Test getting user's logs."""
        user_data = {
            "email": "getlogs_test@example.com",
            "password": "securepassword123",
            "firstName": "GetLogs",
            "lastName": "Test",
            "handle": "getlogstest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        # Create a log entry
        await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15",
                "watchedWhere": "cinema"
            }
        )

        # Get logs (GET is safe, no CSRF needed, cookies auto-sent)
        response = await async_client.get("/v1/logs/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["tmdbId"] == 550
        assert data["logs"][0]["movie"]["tmdbId"] == 550

    async def test_update_log_success(self, async_client):
        """Test updating an existing log entry."""
        user_data = {
            "email": "updatelog_test@example.com",
            "password": "securepassword123",
            "firstName": "UpdateLog",
            "lastName": "Test",
            "handle": "updatelogtest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        # Create a log entry
        create_response = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15",
                "watchedWhere": "cinema"
            }
        )
        assert create_response.status_code == 201
        log_id = create_response.json()["id"]

        # Update the log
        response = await async_client.put(
            f"/v1/logs/{log_id}",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "viewingNotes": "Updated notes!",
                "watchedWhere": "streaming"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["viewingNotes"] == "Updated notes!"
        assert data["watchedWhere"] == "streaming"

    async def test_get_logs_unauthorized(self, async_client):
        """Test getting logs without authentication."""
        response = await async_client.get("/v1/logs/")

        assert response.status_code == 401
