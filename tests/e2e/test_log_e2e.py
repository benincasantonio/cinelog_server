"""
E2E tests for log controller endpoints.
Tests the full stack: FastAPI -> LogService -> MongoDB.
"""
from tests.e2e.conftest import register_and_login
from app.utils.error_codes import ErrorCodes


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

    async def test_get_logs_filter_by_watched_where(self, async_client):
        """Test filtering logs by watchedWhere."""
        user_data = {
            "email": "filter_watchedwhere_test@example.com",
            "password": "securepassword123",
            "firstName": "FilterWhere",
            "lastName": "Test",
            "handle": "filterwheretest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        create_a = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-10",
                "watchedWhere": "cinema"
            }
        )
        assert create_a.status_code == 201

        create_b = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 13,
                "dateWatched": "2024-01-11",
                "watchedWhere": "streaming"
            }
        )
        assert create_b.status_code == 201

        response = await async_client.get("/v1/logs/?watchedWhere=streaming")
        assert response.status_code == 200
        data = response.json()

        assert len(data["logs"]) == 1
        assert data["logs"][0]["watchedWhere"] == "streaming"
        assert data["logs"][0]["tmdbId"] == 13

    async def test_get_logs_filter_by_date_range(self, async_client):
        """Test filtering logs by dateWatchedFrom/dateWatchedTo."""
        user_data = {
            "email": "filter_dates_test@example.com",
            "password": "securepassword123",
            "firstName": "FilterDate",
            "lastName": "Test",
            "handle": "filterdatetest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        create_a = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-05",
                "watchedWhere": "cinema"
            }
        )
        assert create_a.status_code == 201

        create_b = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 13,
                "dateWatched": "2024-01-15",
                "watchedWhere": "streaming"
            }
        )
        assert create_b.status_code == 201

        create_c = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 278,
                "dateWatched": "2024-01-25",
                "watchedWhere": "tv"
            }
        )
        assert create_c.status_code == 201

        bounded_response = await async_client.get(
            "/v1/logs/?dateWatchedFrom=2024-01-10&dateWatchedTo=2024-01-20"
        )
        assert bounded_response.status_code == 200
        bounded_data = bounded_response.json()
        assert len(bounded_data["logs"]) == 1
        assert bounded_data["logs"][0]["dateWatched"] == "2024-01-15"

        partial_response = await async_client.get(
            "/v1/logs/?dateWatchedFrom=2024-01-15"
        )
        assert partial_response.status_code == 200
        partial_data = partial_response.json()
        assert len(partial_data["logs"]) == 2
        assert [log["dateWatched"] for log in partial_data["logs"]] == [
            "2024-01-25",
            "2024-01-15",
        ]

    async def test_get_logs_sort_by_date_watched(self, async_client):
        """Test sorting logs by dateWatched ascending and descending."""
        user_data = {
            "email": "sort_logs_test@example.com",
            "password": "securepassword123",
            "firstName": "SortLogs",
            "lastName": "Test",
            "handle": "sortlogstest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        for tmdb_id, date_watched in [
            (550, "2024-01-20"),
            (13, "2024-01-10"),
            (278, "2024-01-15"),
        ]:
            create_response = await async_client.post(
                "/v1/logs/",
                headers={"X-CSRF-Token": csrf_token},
                json={
                    "tmdbId": tmdb_id,
                    "dateWatched": date_watched,
                    "watchedWhere": "cinema"
                }
            )
            assert create_response.status_code == 201

        asc_response = await async_client.get(
            "/v1/logs/?sortBy=dateWatched&sortOrder=asc"
        )
        assert asc_response.status_code == 200
        asc_data = asc_response.json()
        assert [log["dateWatched"] for log in asc_data["logs"]] == [
            "2024-01-10",
            "2024-01-15",
            "2024-01-20",
        ]

        desc_response = await async_client.get(
            "/v1/logs/?sortBy=dateWatched&sortOrder=desc"
        )
        assert desc_response.status_code == 200
        desc_data = desc_response.json()
        assert [log["dateWatched"] for log in desc_data["logs"]] == [
            "2024-01-20",
            "2024-01-15",
            "2024-01-10",
        ]

    async def test_update_log_invalid_id_returns_not_found(self, async_client):
        """Test updating a non-existent log ID returns LOG_NOT_FOUND."""
        user_data = {
            "email": "update_invalidid_test@example.com",
            "password": "securepassword123",
            "firstName": "UpdateInvalid",
            "lastName": "Test",
            "handle": "updateinvalidtest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        response = await async_client.put(
            "/v1/logs/507f1f77bcf86cd799439011",
            headers={"X-CSRF-Token": csrf_token},
            json={"viewingNotes": "Should fail"}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error_code_name"] == ErrorCodes.LOG_NOT_FOUND.error_code_name

    async def test_update_log_of_other_user_returns_not_found(self, async_client):
        """Test that a user cannot update another user's log."""
        user_a = {
            "email": "owner_user_test@example.com",
            "password": "securepassword123",
            "firstName": "Owner",
            "lastName": "User",
            "handle": "ownerusertest",
            "dateOfBirth": "1990-01-01"
        }
        login_a = await register_and_login(async_client, user_a)
        csrf_token_a = login_a["csrfToken"]

        create_response = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token_a},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15",
                "watchedWhere": "cinema"
            }
        )
        assert create_response.status_code == 201
        log_id = create_response.json()["id"]

        user_b = {
            "email": "intruder_user_test@example.com",
            "password": "securepassword123",
            "firstName": "Intruder",
            "lastName": "User",
            "handle": "intruderusertest",
            "dateOfBirth": "1990-01-01"
        }
        login_b = await register_and_login(async_client, user_b)
        csrf_token_b = login_b["csrfToken"]

        response = await async_client.put(
            f"/v1/logs/{log_id}",
            headers={"X-CSRF-Token": csrf_token_b},
            json={"viewingNotes": "Intruder update"}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error_code_name"] == ErrorCodes.LOG_NOT_FOUND.error_code_name

    async def test_get_logs_empty_for_new_user(self, async_client):
        """Test getting logs for a user with no log entries returns empty list."""
        user_data = {
            "email": "empty_logs_test@example.com",
            "password": "securepassword123",
            "firstName": "EmptyLogs",
            "lastName": "Test",
            "handle": "emptylogstest",
            "dateOfBirth": "1990-01-01"
        }
        await register_and_login(async_client, user_data)

        response = await async_client.get("/v1/logs/")

        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []

    async def test_create_log_invalid_watched_where(self, async_client):
        """Test creating a log with invalid watchedWhere value."""
        user_data = {
            "email": "invalid_watchedwhere_test@example.com",
            "password": "securepassword123",
            "firstName": "InvalidWhere",
            "lastName": "Test",
            "handle": "invalidwheretest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        response = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15",
                "watchedWhere": "invalid-place"
            }
        )

        assert response.status_code == 422
        assert "watchedWhere" in str(response.json())

    async def test_get_logs_user_isolation(self, async_client):
        """Test that a user cannot see another user's logs."""
        user_a = {
            "email": "isolation_owner_test@example.com",
            "password": "securepassword123",
            "firstName": "IsoOwner",
            "lastName": "Test",
            "handle": "isoownertest",
            "dateOfBirth": "1990-01-01"
        }
        login_a = await register_and_login(async_client, user_a)
        csrf_token_a = login_a["csrfToken"]

        create_resp = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token_a},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15",
                "watchedWhere": "cinema"
            }
        )
        assert create_resp.status_code == 201

        user_b = {
            "email": "isolation_viewer_test@example.com",
            "password": "securepassword123",
            "firstName": "IsoViewer",
            "lastName": "Test",
            "handle": "isoviewertest",
            "dateOfBirth": "1990-01-01"
        }
        await register_and_login(async_client, user_b)

        response = await async_client.get("/v1/logs/")
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []

    async def test_create_log_reuses_existing_movie(self, async_client):
        """Test that logging the same TMDB ID twice reuses the same movie."""
        user_data = {
            "email": "reuse_movie_test@example.com",
            "password": "securepassword123",
            "firstName": "ReuseMovie",
            "lastName": "Test",
            "handle": "reusemovietest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        first_resp = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-10",
                "watchedWhere": "cinema"
            }
        )
        assert first_resp.status_code == 201
        first_data = first_resp.json()

        second_resp = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-02-20",
                "watchedWhere": "streaming"
            }
        )
        assert second_resp.status_code == 201
        second_data = second_resp.json()

        # Two distinct log entries
        assert first_data["id"] != second_data["id"]
        # Both reference the same movie
        assert first_data["movieId"] == second_data["movieId"]

        # Verify 2 logs exist
        logs_resp = await async_client.get("/v1/logs/")
        assert logs_resp.status_code == 200
        assert len(logs_resp.json()["logs"]) == 2

    async def test_update_log_unauthorized(self, async_client):
        """Test updating a log without authentication."""
        response = await async_client.put(
            "/v1/logs/507f1f77bcf86cd799439011",
            json={"viewingNotes": "Should fail"}
        )
        assert response.status_code in [401, 403]

    async def test_update_log_invalid_watched_where(self, async_client):
        """Test updating a log with invalid watchedWhere value."""
        user_data = {
            "email": "update_invalidwhere_test@example.com",
            "password": "securepassword123",
            "firstName": "UpdInvalid",
            "lastName": "Test",
            "handle": "updinvalidwheretest",
            "dateOfBirth": "1990-01-01"
        }
        login_data = await register_and_login(async_client, user_data)
        csrf_token = login_data["csrfToken"]

        create_resp = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "tmdbId": 550,
                "dateWatched": "2024-01-15",
                "watchedWhere": "cinema"
            }
        )
        assert create_resp.status_code == 201
        log_id = create_resp.json()["id"]

        response = await async_client.put(
            f"/v1/logs/{log_id}",
            headers={"X-CSRF-Token": csrf_token},
            json={"watchedWhere": "invalid-place"}
        )

        assert response.status_code == 422
        assert "watchedWhere" in str(response.json())
