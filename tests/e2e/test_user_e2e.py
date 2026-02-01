"""
E2E tests for user controller endpoints.
Tests the full stack: FastAPI -> UserService -> Firebase + MongoDB.
"""
from tests.e2e.conftest import get_firebase_id_token


class TestUserE2E:
    """E2E tests for user controller endpoints."""

    async def test_get_user_info_success(self, async_client):
        """Test getting user info for authenticated user."""
        # First, register a user
        register_response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "userinfo_test@example.com",
                "password": "securepassword123",
                "firstName": "UserInfo",
                "lastName": "Test",
                "handle": "userinfotest",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert register_response.status_code == 200
        user_data = register_response.json()
        
        # Get Firebase ID token from emulator
        id_token = get_firebase_id_token("userinfo_test@example.com", "securepassword123")
        
        # Get user info
        response = await async_client.get(
            "/v1/users/info",
            headers={"Authorization": f"Bearer {id_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "userinfo_test@example.com"
        assert data["firstName"] == "UserInfo"
        assert data["lastName"] == "Test"
        assert data["handle"] == "userinfotest"
        assert data["id"] == user_data["userId"]

    async def test_get_user_info_unauthorized(self, async_client):
        """Test getting user info without authentication."""
        response = await async_client.get("/v1/users/info")
        
        assert response.status_code == 401

    async def test_get_user_info_invalid_token(self, async_client):
        """Test getting user info with invalid token."""
        response = await async_client.get(
            "/v1/users/info",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401

    async def test_get_user_logs_empty(self, async_client):
        """Test getting user logs when user has no logs."""
        # Register a user
        register_response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "userlogs_test@example.com",
                "password": "securepassword123",
                "firstName": "UserLogs",
                "lastName": "Test",
                "handle": "userlogstest",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data["userId"]
        
        # Get Firebase ID token
        id_token = get_firebase_id_token("userlogs_test@example.com", "securepassword123")
        
        # Get user logs
        response = await async_client.get(
            f"/v1/users/{user_id}/logs",
            headers={"Authorization": f"Bearer {id_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []

    async def test_get_user_logs_unauthorized(self, async_client):
        """Test getting user logs without authentication."""
        response = await async_client.get("/v1/users/some-user-id/logs")
        
        assert response.status_code == 401

    async def test_get_user_logs_with_data(self, async_client):
        """Test getting user logs when user has logs with movie data."""
        # Register a user
        register_response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "userlogs_data@example.com",
                "password": "securepassword123",
                "firstName": "UserLogsData",
                "lastName": "Test",
                "handle": "userlogsdatatest",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data["userId"]
        
        # Get Firebase ID token
        id_token = get_firebase_id_token("userlogs_data@example.com", "securepassword123")
        
        # Create a log entry (this creates a movie too)
        log_response = await async_client.post(
            "/v1/logs/",
            headers={"Authorization": f"Bearer {id_token}"},
            json={
                "tmdbId": 550,  # Fight Club
                "dateWatched": "2024-01-15",
                "viewingNotes": "Great movie!",
                "watchedWhere": "cinema"
            }
        )
        assert log_response.status_code == 200
        
        # Get user logs via user controller endpoint
        response = await async_client.get(
            f"/v1/users/{user_id}/logs",
            headers={"Authorization": f"Bearer {id_token}"}
        )
        
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
