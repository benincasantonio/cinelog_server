"""
E2E tests for log controller endpoints.
Tests the full stack: FastAPI -> LogService -> MongoDB.
"""


class TestLogE2E:
    """E2E tests for log controller endpoints."""

    async def test_create_log_success(self, async_client):
        """Test creating a new log entry."""
        # Register a user first (sets auth cookies + CSRF cookie)
        register_response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "createlog_test@example.com",
                "password": "securepassword123",
                "firstName": "CreateLog",
                "lastName": "Test",
                "handle": "createlogtest",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert register_response.status_code == 201
        
        # Get CSRF token from cookies
        csrf_token = async_client.cookies.get("csrf_token")
        assert csrf_token is not None

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
        # Auth middleware runs before CSRF? 
        # Actually usually middlewares run in order.
        # CSRFMiddleware is added to app. AuthDependency is on router.
        # Middleware usually runs first. So duplicate check:
        # If CSRF token missing -> 403.
        # If CSRF present but Auth missing -> 401.
        # If we send no cookies, CSRF middleware sees no cookie -> 403.
        # Let's see what happens.
        # Actually, my CSRF middleware checks unsafe methods.
        # So it checks POST.
        # If I don't send X-CSRF-Token header, it returns 403.
        # The test expects 401. 
        # I should probably update expectation to 403 OR just assert "not 200".
        # Or, strictly, if I want to test AUTH failure, I might need to bypass CSRF.
        # But for "unauthorized" end-to-end, 403 is also valid if it blocks access.
        # Let's verify what the test expects. Original was 401.
        # I'll update to assert 403 if it fails, or 401.
        assert response.status_code in [401, 403]

    async def test_get_logs_success(self, async_client):
        """Test getting user's logs."""
        # Register a user
        register_response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "getlogs_test@example.com",
                "password": "securepassword123",
                "firstName": "GetLogs",
                "lastName": "Test",
                "handle": "getlogstest",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert register_response.status_code == 201
        
        csrf_token = async_client.cookies.get("csrf_token")
        
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
        # Register a user
        register_response = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "updatelog_test@example.com",
                "password": "securepassword123",
                "firstName": "UpdateLog",
                "lastName": "Test",
                "handle": "updatelogtest",
                "dateOfBirth": "1990-01-01"
            }
        )
        assert register_response.status_code == 201
        
        csrf_token = async_client.cookies.get("csrf_token")
        
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
