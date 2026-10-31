"""
E2E data-consistency tests for movie identity across logs and ratings.

Assertions go through the API wherever it exposes the fact. PostgreSQL is read only to
count `movies` rows for a TMDB id, because no endpoint can show a duplicate movie.
"""

import asyncio

from sqlalchemy import text

from tests.e2e.conftest import count_movie_rows, logged_in_client, movie_ref_for, resolve_movie

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


async def _resolve(client, csrf_token: str):
    return await client.post(
        "/v1/movies/resolve", headers={"X-CSRF-Token": csrf_token}, json={"movieRef": movie_ref_for(TMDB_ID)}
    )


async def _create_log(client, csrf_token: str, movie_id: str, **fields):
    return await client.post(
        "/v1/logs/",
        headers={"X-CSRF-Token": csrf_token},
        json={"movieId": movie_id, "dateWatched": "2024-01-15", "watchedWhere": "cinema", **fields},
    )


async def _rate(client, csrf_token: str, movie_id: str, rating: int):
    return await client.post(
        "/v1/movie-ratings/",
        headers={"X-CSRF-Token": csrf_token},
        json={"movieId": movie_id, "rating": rating},
    )


def _detail_imports(fake_movie_provider) -> int:
    return sum(request.external_id == str(TMDB_ID) for request in fake_movie_provider.detail_requests)


class TestConcurrentFirstImport:
    """Concurrent first selections of an unseen movie import it exactly once."""

    async def test_concurrent_resolves_converge_on_one_movie(self, async_client, postgres_engine, fake_movie_provider):
        # Both requests miss the catalog and reach the provider before either stores the movie.
        fake_movie_provider.detail_barrier = asyncio.Barrier(2)

        async with (
            logged_in_client(async_client, _user_payload("concurrent_a")) as (client_a, csrf_a),
            logged_in_client(async_client, _user_payload("concurrent_b")) as (client_b, csrf_b),
        ):
            first, second = await asyncio.gather(_resolve(client_a, csrf_a), _resolve(client_b, csrf_b))
            fake_movie_provider.detail_barrier = None
            movie_id = first.json()["movieId"]
            log = await _create_log(client_a, csrf_a, movie_id)
            rating = await _rate(client_b, csrf_b, movie_id, 7)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert _detail_imports(fake_movie_provider) == 2
        assert await count_movie_rows(postgres_engine, TMDB_ID) == 1
        async with postgres_engine.connect() as connection:
            assert (await connection.execute(text("SELECT count(*) FROM movies"))).scalar_one() == 1
        assert log.status_code == 201
        assert rating.status_code == 200
        assert log.json()["movieId"] == rating.json()["movieId"] == movie_id


class TestRepeatedResolve:
    async def test_repeated_resolve_returns_the_same_uuid_without_refreshing(
        self, async_client, postgres_engine, fake_movie_provider
    ):
        async with logged_in_client(async_client, _user_payload("repeat")) as (client, csrf):
            first = await _resolve(client, csrf)
            second = await _resolve(client, csrf)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert _detail_imports(fake_movie_provider) == 1
        assert await count_movie_rows(postgres_engine, TMDB_ID) == 1


class TestRewatchesInTheLogList:
    async def test_logging_a_movie_twice_keeps_one_movie_and_shows_its_rating(
        self, async_client, postgres_engine, fake_movie_provider
    ):
        user = _user_payload("rewatch")
        async with logged_in_client(async_client, user) as (client, csrf):
            movie_id = await resolve_movie(client, csrf, TMDB_ID)
            first = await _create_log(client, csrf, movie_id)
            second = await _create_log(client, csrf, movie_id, dateWatched="2024-02-20")
            await _rate(client, csrf, movie_id, 9)
            listing = await client.get(f"/v1/logs/{user['handle']}")

        assert first.status_code == second.status_code == 201
        assert first.json()["movieId"] == second.json()["movieId"] == movie_id
        assert _detail_imports(fake_movie_provider) == 1
        assert await count_movie_rows(postgres_engine, TMDB_ID) == 1

        assert listing.status_code == 200
        body = listing.json()
        assert (body["totalWatches"], body["uniqueTitles"], body["totalRewatches"]) == (2, 1, 1)
        assert {item["id"] for item in body["logs"]} == {first.json()["id"], second.json()["id"]}
        assert [item["movieRating"] for item in body["logs"]] == [9, 9]
