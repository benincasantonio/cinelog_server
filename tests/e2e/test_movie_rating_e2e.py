"""
E2E tests for movie rating controller endpoints.
Tests the full stack against the selected e2e backend.
"""

from tests.e2e.conftest import register_and_login, resolve_movie


def _user_payload(email: str, handle: str) -> dict:
    return {
        "email": email,
        "password": "securepassword123",
        "firstName": "First",
        "lastName": "Last",
        "handle": handle,
        "dateOfBirth": "1990-01-01",
        "locale": "en-US",
    }


class TestMovieRatingE2E:
    """Owner-only behavior of GET /v1/movie-ratings/{movie_id}."""

    async def test_owner_reads_own_rating(self, async_client):
        """Owner can read their own rating."""
        login = await register_and_login(async_client, _user_payload("rating_owner@example.com", "ratingowner"))

        movie_id = await resolve_movie(async_client, login["csrfToken"], 550)
        create_resp = await async_client.post(
            "/v1/movie-ratings/",
            headers={"X-CSRF-Token": login["csrfToken"]},
            json={"movieId": movie_id, "rating": 9, "comment": "Great"},
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["movieId"] == movie_id

        response = await async_client.get(f"/v1/movie-ratings/{movie_id}")

        assert response.status_code == 200
        assert response.json()["rating"] == 9

    async def test_returns_204_when_no_rating(self, async_client):
        """GET returns 204 No Content when the caller has no rating for an existing movie."""
        login = await register_and_login(async_client, _user_payload("rating_empty@example.com", "ratingempty"))
        movie_id = await resolve_movie(async_client, login["csrfToken"], 550)

        response = await async_client.get(f"/v1/movie-ratings/{movie_id}")

        assert response.status_code == 204
        assert response.content == b""
