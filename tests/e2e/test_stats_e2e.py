"""E2E coverage for the PostgreSQL-backed user statistics endpoint."""

from tests.e2e.conftest import register_and_login


def _user_payload(email: str, handle: str) -> dict:
    return {
        "email": email,
        "password": "securepassword123",
        "firstName": "Stats",
        "lastName": "User",
        "handle": handle,
        "dateOfBirth": "1990-01-01",
    }


async def _create_log(
    client,
    headers: dict,
    *,
    tmdb_id: int,
    watched_at: str,
    watched_where: str,
) -> dict:
    response = await client.post(
        "/v1/logs/",
        headers=headers,
        json={
            "tmdbId": tmdb_id,
            "dateWatched": watched_at,
            "watchedWhere": watched_where,
        },
    )
    assert response.status_code == 201
    return response.json()


async def _rate_movie(client, headers: dict, *, tmdb_id: int, rating: int) -> None:
    response = await client.post(
        "/v1/movie-ratings/",
        headers=headers,
        json={"tmdbId": tmdb_id, "rating": rating},
    )
    assert response.status_code == 200


class TestStatsE2E:
    async def test_stats_aggregate_rewatches_ratings_distribution_and_year_filter(
        self,
        async_client,
    ):
        login = await register_and_login(
            async_client,
            _user_payload("stats_full@example.com", "statsfull"),
        )
        headers = {"X-CSRF-Token": login["csrfToken"]}

        for tmdb_id, watched_at, watched_where in [
            (550, "2023-12-31", "cinema"),
            (550, "2024-01-01", "streaming"),
            (13, "2024-12-31", "homeVideo"),
        ]:
            await _create_log(
                async_client,
                headers,
                tmdb_id=tmdb_id,
                watched_at=watched_at,
                watched_where=watched_where,
            )

        for tmdb_id, rating in [(550, 9), (13, 7)]:
            await _rate_movie(async_client, headers, tmdb_id=tmdb_id, rating=rating)

        all_time_response = await async_client.get("/v1/stats/me")
        assert all_time_response.status_code == 200
        all_time = all_time_response.json()
        assert all_time["summary"] == {
            "totalWatches": 3,
            "uniqueTitles": 2,
            "totalRewatches": 1,
            "totalMinutes": 360,
            "voteAverage": 8.0,
        }
        assert all_time["distribution"]["byMethod"] == {
            "cinema": 1,
            "streaming": 1,
            "homeVideo": 1,
            "tv": 0,
            "other": 0,
        }
        assert all_time["pace"] == {
            "onTrackFor": 0,
            "currentAverage": 0.0,
            "daysSinceLastLog": 0,
        }

        year_response = await async_client.get("/v1/stats/me?yearFrom=2024&yearTo=2024")
        assert year_response.status_code == 200
        year_stats = year_response.json()
        assert year_stats["summary"] == {
            "totalWatches": 2,
            "uniqueTitles": 2,
            "totalRewatches": 0,
            "totalMinutes": 240,
            "voteAverage": 8.0,
        }
        assert year_stats["distribution"]["byMethod"] == {
            "cinema": 0,
            "streaming": 1,
            "homeVideo": 1,
            "tv": 0,
            "other": 0,
        }

    async def test_stats_returns_empty_response_for_user_without_logs(self, async_client):
        await register_and_login(
            async_client,
            _user_payload("stats_empty@example.com", "statsempty"),
        )

        response = await async_client.get("/v1/stats/me")

        assert response.status_code == 200
        assert response.json()["summary"] == {
            "totalWatches": 0,
            "uniqueTitles": 0,
            "totalRewatches": 0,
            "totalMinutes": 0,
            "voteAverage": None,
        }

    async def test_stats_support_partial_year_bounds_and_unrated_movies(self, async_client):
        login = await register_and_login(
            async_client,
            _user_payload("stats_partial_year@example.com", "statspartialyear"),
        )
        headers = {"X-CSRF-Token": login["csrfToken"]}

        for tmdb_id, watched_at in [
            (101, "2023-06-15"),
            (102, "2024-06-15"),
            (103, "2025-06-15"),
        ]:
            await _create_log(
                async_client,
                headers,
                tmdb_id=tmdb_id,
                watched_at=watched_at,
                watched_where="other",
            )

        from_2024 = await async_client.get("/v1/stats/me?yearFrom=2024")
        assert from_2024.status_code == 200
        assert from_2024.json()["summary"] == {
            "totalWatches": 2,
            "uniqueTitles": 2,
            "totalRewatches": 0,
            "totalMinutes": 240,
            "voteAverage": None,
        }

        through_2024 = await async_client.get("/v1/stats/me?yearTo=2024")
        assert through_2024.status_code == 200
        assert through_2024.json()["summary"] == {
            "totalWatches": 2,
            "uniqueTitles": 2,
            "totalRewatches": 0,
            "totalMinutes": 240,
            "voteAverage": None,
        }

    async def test_stats_are_isolated_by_authenticated_user(self, async_client):
        first_login = await register_and_login(
            async_client,
            _user_payload("stats_first@example.com", "statsfirst"),
        )
        await _create_log(
            async_client,
            {"X-CSRF-Token": first_login["csrfToken"]},
            tmdb_id=201,
            watched_at="2024-01-01",
            watched_where="cinema",
        )
        first_stats = await async_client.get("/v1/stats/me")
        assert first_stats.status_code == 200
        assert first_stats.json()["distribution"]["byMethod"]["cinema"] == 1

        second_login = await register_and_login(
            async_client,
            _user_payload("stats_second@example.com", "statssecond"),
        )
        await _create_log(
            async_client,
            {"X-CSRF-Token": second_login["csrfToken"]},
            tmdb_id=202,
            watched_at="2024-01-02",
            watched_where="tv",
        )
        second_stats = await async_client.get("/v1/stats/me")
        assert second_stats.status_code == 200
        assert second_stats.json()["distribution"]["byMethod"] == {
            "cinema": 0,
            "streaming": 0,
            "homeVideo": 0,
            "tv": 1,
            "other": 0,
        }

        login_response = await async_client.post(
            "/v1/auth/login",
            json={"email": "stats_first@example.com", "password": "securepassword123"},
        )
        assert login_response.status_code == 200

        restored_first_stats = await async_client.get("/v1/stats/me")
        assert restored_first_stats.status_code == 200
        assert restored_first_stats.json()["distribution"]["byMethod"] == {
            "cinema": 1,
            "streaming": 0,
            "homeVideo": 0,
            "tv": 0,
            "other": 0,
        }

    async def test_cached_stats_are_invalidated_by_rating_and_log_writes(self, async_client):
        login = await register_and_login(
            async_client,
            _user_payload("stats_invalidation@example.com", "statsinvalidation"),
        )
        headers = {"X-CSRF-Token": login["csrfToken"]}

        first_log = await _create_log(
            async_client,
            headers,
            tmdb_id=301,
            watched_at="2024-01-01",
            watched_where="cinema",
        )

        initial_stats = await async_client.get("/v1/stats/me")
        assert initial_stats.status_code == 200
        assert initial_stats.json()["summary"]["voteAverage"] is None

        await _rate_movie(async_client, headers, tmdb_id=301, rating=9)

        rated_stats = await async_client.get("/v1/stats/me")
        assert rated_stats.status_code == 200
        assert rated_stats.json()["summary"]["voteAverage"] == 9.0

        second_log = await _create_log(
            async_client,
            headers,
            tmdb_id=302,
            watched_at="2024-01-02",
            watched_where="streaming",
        )

        expanded_stats = await async_client.get("/v1/stats/me")
        assert expanded_stats.status_code == 200
        assert expanded_stats.json()["summary"] == {
            "totalWatches": 2,
            "uniqueTitles": 2,
            "totalRewatches": 0,
            "totalMinutes": 240,
            "voteAverage": 9.0,
        }

        delete_response = await async_client.delete(
            f"/v1/logs/{second_log['id']}",
            headers=headers,
        )
        assert delete_response.status_code == 204

        reduced_stats = await async_client.get("/v1/stats/me")
        assert reduced_stats.status_code == 200
        assert reduced_stats.json()["summary"] == {
            "totalWatches": 1,
            "uniqueTitles": 1,
            "totalRewatches": 0,
            "totalMinutes": 120,
            "voteAverage": 9.0,
        }
        assert first_log["id"] != second_log["id"]
