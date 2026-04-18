"""
E2E tests for movie rating controller endpoints.
Tests the full stack: FastAPI -> MovieRatingService -> MongoDB.
"""

from tests.e2e.conftest import register_and_login


def _user_payload(email: str, handle: str) -> dict:
    return {
        "email": email,
        "password": "securepassword123",
        "firstName": "First",
        "lastName": "Last",
        "handle": handle,
        "dateOfBirth": "1990-01-01",
    }


class TestMovieRatingE2E:
    """Owner-only behavior of GET /v1/movie-ratings/{tmdb_id}."""

    async def test_owner_reads_own_rating(self, async_client):
        """Owner can read their own rating."""
        login = await register_and_login(
            async_client, _user_payload("rating_owner@example.com", "ratingowner")
        )

        create_resp = await async_client.post(
            "/v1/movie-ratings/",
            headers={"X-CSRF-Token": login["csrfToken"]},
            json={"tmdbId": 550, "rating": 9, "comment": "Great"},
        )
        assert create_resp.status_code == 200

        response = await async_client.get("/v1/movie-ratings/550")

        assert response.status_code == 200
        assert response.json()["rating"] == 9

    async def test_returns_204_when_no_rating(self, async_client):
        """GET returns 204 No Content when the caller has no rating for the tmdb_id."""
        await register_and_login(
            async_client, _user_payload("rating_empty@example.com", "ratingempty")
        )

        response = await async_client.get("/v1/movie-ratings/550")

        assert response.status_code == 204
        assert response.content == b""
