"""
E2E data-consistency tests for movie identity across logs and ratings.

Assertions go through the API wherever it exposes the fact. PostgreSQL is read only to
count `movies` rows for a TMDB id, because no endpoint can show a duplicate movie.
"""

import asyncio

import pytest

from tests.e2e.conftest import count_movie_rows, logged_in_client

TMDB_ID = 550


def _user_payload(name: str) -> dict:
    return {
        "email": f"{name}@example.com",
        "password": "securepassword123",
        "firstName": "Identity",
        "lastName": "User",
        "handle": name,
        "dateOfBirth": "1990-01-01",
        "locale": "en-US",
    }


async def _create_log(client, csrf_token: str, **fields):
    return await client.post(
        "/v1/logs/",
        headers={"X-CSRF-Token": csrf_token},
        json={"tmdbId": TMDB_ID, "dateWatched": "2024-01-15", "watchedWhere": "cinema", **fields},
    )


async def _rate(client, csrf_token: str, rating: int):
    return await client.post(
        "/v1/movie-ratings/",
        headers={"X-CSRF-Token": csrf_token},
        json={"tmdbId": TMDB_ID, "rating": rating},
    )


def _detail_imports(fake_movie_provider) -> int:
    return sum(request.external_id == str(TMDB_ID) for request in fake_movie_provider.detail_requests)


class TestConcurrentFirstImport:
    """Concurrent first writes for an unseen movie import it exactly once."""

    @pytest.mark.parametrize("second_write", ["log", "rating"])
    async def test_concurrent_writes_converge_on_one_movie(
        self, async_client, postgres_engine, fake_movie_provider, second_write
    ):
        # Both requests miss the catalog and reach the provider before either stores the movie.
        fake_movie_provider.detail_barrier = asyncio.Barrier(2)

        async with (
            logged_in_client(async_client, _user_payload("concurrent_a")) as (client_a, csrf_a),
            logged_in_client(async_client, _user_payload("concurrent_b")) as (client_b, csrf_b),
        ):
            second = _create_log(client_b, csrf_b) if second_write == "log" else _rate(client_b, csrf_b, 7)
            first_response, second_response = await asyncio.gather(_create_log(client_a, csrf_a), second)

        assert first_response.status_code == 201
        assert second_response.status_code == (201 if second_write == "log" else 200)
        assert first_response.json()["movieId"] == second_response.json()["movieId"]
        assert _detail_imports(fake_movie_provider) == 2
        assert await count_movie_rows(postgres_engine, TMDB_ID) == 1


class TestRewatchesInTheLogList:
    async def test_logging_a_movie_twice_keeps_one_movie_and_shows_its_rating(
        self, async_client, postgres_engine, fake_movie_provider
    ):
        user = _user_payload("rewatch")
        async with logged_in_client(async_client, user) as (client, csrf):
            first = await _create_log(client, csrf)
            second = await _create_log(client, csrf, dateWatched="2024-02-20")
            await _rate(client, csrf, 9)
            listing = await client.get(f"/v1/logs/{user['handle']}")

        assert first.status_code == second.status_code == 201
        assert first.json()["movieId"] == second.json()["movieId"]
        assert _detail_imports(fake_movie_provider) == 1
        assert await count_movie_rows(postgres_engine, TMDB_ID) == 1

        assert listing.status_code == 200
        body = listing.json()
        assert (body["totalWatches"], body["uniqueTitles"], body["totalRewatches"]) == (2, 1, 1)
        assert {item["id"] for item in body["logs"]} == {first.json()["id"], second.json()["id"]}
        assert [item["movieRating"] for item in body["logs"]] == [9, 9]
