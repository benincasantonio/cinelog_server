from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.repository.movie_repository import MovieRepository
from app.schemas.movie_provider_schemas import MovieDetailsQuery, MovieSearchQuery, MovieSourceReferenceDTO
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException
from tests.e2e.conftest import movie_ref_for, register_and_login, resolve_movie
from tests.fakes.movie_provider import OBSERVED_AT

USER = {
    "email": "provider@example.com",
    "password": "securepassword123",
    "firstName": "Movie",
    "lastName": "Provider",
    "handle": "movieprovider",
    "dateOfBirth": "1990-01-01",
    "locale": "it-IT",
    "profileVisibility": "public",
}

SEARCH_ITEM_FIELDS = {
    "title": "Movie 550",
    "overview": "Mocked movie details",
    "releaseDate": "2024-01-01",
    "posterPath": "/poster.jpg",
    "voteAverage": 7.5,
    "backdropPath": "/backdrop.jpg",
    "genreIds": [],
    "originalLanguage": "en",
    "originalTitle": "Movie 550",
}


async def _catalog_counts(postgres_engine) -> tuple[int, int]:
    async with postgres_engine.connect() as connection:
        movies = (await connection.execute(text("SELECT count(*) FROM movies"))).scalar_one()
        mappings = (await connection.execute(text("SELECT count(*) FROM movie_providers"))).scalar_one()
        return movies, mappings


async def test_search_resolve_detail_and_repeat_writes(async_client, fake_movie_provider, postgres_engine):
    login = await register_and_login(async_client, USER)
    headers = {"X-CSRF-Token": login["csrfToken"]}

    search = await async_client.get(
        "/v1/movies/search", params={"query": "Movie"}, headers={"Accept-Language": "fr-FR"}
    )
    assert search.status_code == 200
    assert search.json() == {
        "results": [{"id": None, "movieRef": movie_ref_for(550), **SEARCH_ITEM_FIELDS}],
        "nextCursor": None,
    }
    assert fake_movie_provider.search_requests == [MovieSearchQuery(query="Movie", locale="fr-FR")]
    # Searching never imports or fetches details.
    assert fake_movie_provider.detail_requests == []
    assert await _catalog_counts(postgres_engine) == (0, 0)

    resolved = await async_client.post(
        "/v1/movies/resolve", headers=headers, json={"movieRef": search.json()["results"][0]["movieRef"]}
    )
    assert resolved.status_code == 200
    movie_id = resolved.json()["movieId"]
    assert resolved.json() == {"movieId": movie_id}
    assert fake_movie_provider.detail_requests == [MovieDetailsQuery(external_id="550", locale="en-US")]
    assert await _catalog_counts(postgres_engine) == (1, 1)

    fake_movie_provider.detail_requests.clear()
    detail = await async_client.get(f"/v1/movies/{movie_id}", headers={"Accept-Language": "it-IT"})
    assert detail.status_code == 200
    assert detail.json() == {
        "id": movie_id,
        "title": "Movie 550",
        "originalTitle": "Movie 550",
        "overview": "Mocked movie details",
        "releaseDate": "2024-01-01",
        "posterPath": "/poster.jpg",
        "backdropPath": "/backdrop.jpg",
        "voteAverage": 7.5,
        "voteCount": 1000,
        "runtime": 120,
        "budget": 50000000,
        "revenue": 100000000,
        "status": "Released",
        "tagline": "Mocked tagline",
        "homepage": None,
        "imdbId": None,
        "originalLanguage": "en",
        "popularity": 50.5,
        "adult": False,
        "genres": [],
        "productionCompanies": [],
        "productionCountries": [],
        "spokenLanguages": [],
    }
    assert fake_movie_provider.detail_requests == [MovieDetailsQuery(external_id="550", locale="it-IT")]

    # Once imported, search names the film by its UUID instead of a reference.
    search_again = await async_client.get(
        "/v1/movies/search", params={"query": "Movie"}, headers={"Accept-Language": "fr-FR"}
    )
    assert search_again.json()["results"] == [{"id": movie_id, "movieRef": None, **SEARCH_ITEM_FIELDS}]

    fake_movie_provider.detail_requests.clear()
    ids = []
    for _ in range(2):
        logged = await async_client.post(
            "/v1/logs/",
            headers=headers,
            json={"movieId": movie_id, "dateWatched": "2024-01-01", "watchedWhere": "cinema"},
        )
        assert logged.status_code == 201
        assert "tmdbId" not in logged.json()
        assert "tmdbId" not in logged.json()["movie"]
        ids.append(logged.json()["movieId"])
    assert ids == [movie_id, movie_id]
    # Writes never contact the provider.
    assert fake_movie_provider.detail_requests == []
    stored = await MovieRepository().find_movie_by_provider(MovieSourceReferenceDTO(source="tmdb", external_id="550"))
    assert str(stored.id) == movie_id
    assert stored.providers[0].last_synced_at == OBSERVED_AT
    assert stored.providers[0].payload == {"fixture": "opaque snapshot"}


async def test_second_user_resolve_reuses_movie_imported_by_first_user(async_client, fake_movie_provider):
    users = [
        {**USER, "email": f"provider-{suffix}@example.com", "handle": f"movieprovider{suffix}"} for suffix in ("a", "b")
    ]
    movie_ids = []
    log_ids = []
    for user in users:
        # Logging in replaces the shared client's auth cookies, so each log is written by its own user.
        login = await register_and_login(async_client, user)
        movie_id = await resolve_movie(async_client, login["csrfToken"], 550)
        logged = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": login["csrfToken"]},
            json={"movieId": movie_id, "dateWatched": "2024-01-01", "watchedWhere": "cinema"},
        )
        assert logged.status_code == 201
        movie_ids.append(logged.json()["movieId"])
        log_ids.append(logged.json()["id"])

    assert movie_ids[0] == movie_ids[1]
    assert log_ids[0] != log_ids[1]
    # Only the first user's resolution imports the movie; the second reuses the stored row.
    assert fake_movie_provider.detail_requests == [MovieDetailsQuery(external_id="550", locale="en-US")]

    for user, log_id in zip(users, log_ids, strict=True):
        logs = await async_client.get(f"/v1/logs/{user['handle']}")
        assert logs.status_code == 200
        assert [log["id"] for log in logs.json()["logs"]] == [log_id]


@pytest.mark.parametrize(
    "error",
    [
        ErrorCodes.PROVIDER_MOVIE_NOT_FOUND,
        ErrorCodes.MOVIE_PROVIDER_UNAVAILABLE,
        ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE,
    ],
)
async def test_provider_errors_have_application_shape(async_client, fake_movie_provider, error):
    login = await register_and_login(async_client, USER)
    movie_id = await resolve_movie(async_client, login["csrfToken"], 550)
    fake_movie_provider.get_movie_details = AsyncMock(side_effect=AppException(error))
    response = await async_client.get(f"/v1/movies/{movie_id}", headers={"Accept-Language": "en-US"})
    assert response.status_code == error.error_code
    assert response.json() == {
        "error_code_name": error.error_code_name,
        "error_code": error.error_code,
        "error_message": error.error_message,
        "error_description": error.error_description,
    }


@pytest.mark.parametrize(
    "error",
    [
        ErrorCodes.PROVIDER_MOVIE_NOT_FOUND,
        ErrorCodes.MOVIE_PROVIDER_UNAVAILABLE,
        ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE,
    ],
)
async def test_failed_first_import_leaves_no_catalog_rows(async_client, fake_movie_provider, postgres_engine, error):
    login = await register_and_login(async_client, USER)
    fake_movie_provider.get_movie_details = AsyncMock(side_effect=AppException(error))
    response = await async_client.post(
        "/v1/movies/resolve", headers={"X-CSRF-Token": login["csrfToken"]}, json={"movieRef": movie_ref_for(550)}
    )
    assert response.status_code == error.error_code
    assert response.json()["error_code_name"] == error.error_code_name
    assert await _catalog_counts(postgres_engine) == (0, 0)


@pytest.mark.parametrize("movie_ref", ["tmdb:550", "550", movie_ref_for(550)[:-2] + "xx"])
async def test_invalid_movie_ref_is_rejected_without_import(
    async_client, fake_movie_provider, postgres_engine, movie_ref
):
    login = await register_and_login(async_client, USER)
    response = await async_client.post(
        "/v1/movies/resolve", headers={"X-CSRF-Token": login["csrfToken"]}, json={"movieRef": movie_ref}
    )
    assert response.status_code == 422
    assert response.json()["error_code_name"] == "INVALID_MOVIE_REF"
    assert fake_movie_provider.detail_requests == []
    assert await _catalog_counts(postgres_engine) == (0, 0)


async def test_removed_numeric_routes_and_tmdb_id_writes_are_rejected_without_side_effects(
    async_client, fake_movie_provider, postgres_engine
):
    login = await register_and_login(async_client, USER)
    headers = {"X-CSRF-Token": login["csrfToken"]}

    for url in ["/v1/movies/550", "/v1/movie-ratings/550", "/v1/movies/not-a-uuid"]:
        response = await async_client.get(url, headers={"Accept-Language": "en-US"})
        assert response.status_code == 422, url

    valid_id = str(uuid4())
    for url, body in [
        ("/v1/logs/", {"tmdbId": 550, "dateWatched": "2024-01-01"}),
        ("/v1/logs/", {"movieId": valid_id, "tmdbId": 550, "dateWatched": "2024-01-01"}),
        ("/v1/movie-ratings/", {"tmdbId": 550, "rating": 8}),
        ("/v1/movie-ratings/", {"movieId": valid_id, "tmdbId": 550, "rating": 8}),
        ("/v1/movies/resolve", {"movieRef": movie_ref_for(550), "tmdbId": 550}),
    ]:
        response = await async_client.post(url, headers=headers, json=body)
        assert response.status_code == 422, body

    assert fake_movie_provider.detail_requests == []
    assert await _catalog_counts(postgres_engine) == (0, 0)
    async with postgres_engine.connect() as connection:
        assert (await connection.execute(text("SELECT count(*) FROM logs"))).scalar_one() == 0
        assert (await connection.execute(text("SELECT count(*) FROM movie_ratings"))).scalar_one() == 0


async def test_unknown_movie_uuid_is_not_found(async_client, fake_movie_provider):
    login = await register_and_login(async_client, USER)
    headers = {"X-CSRF-Token": login["csrfToken"]}
    unknown = str(uuid4())

    detail = await async_client.get(f"/v1/movies/{unknown}", headers={"Accept-Language": "en-US"})
    rating = await async_client.get(f"/v1/movie-ratings/{unknown}")
    log = await async_client.post("/v1/logs/", headers=headers, json={"movieId": unknown, "dateWatched": "2024-01-01"})
    rate = await async_client.post("/v1/movie-ratings/", headers=headers, json={"movieId": unknown, "rating": 8})

    for response in (detail, rating, log, rate):
        assert response.status_code == 404
        assert response.json()["error_code_name"] == "MOVIE_NOT_FOUND"
    assert fake_movie_provider.detail_requests == []


async def test_deleted_movie_keeps_history_identity_and_rejects_new_access(
    async_client, fake_movie_provider, postgres_engine
):
    login = await register_and_login(async_client, USER)
    headers = {"X-CSRF-Token": login["csrfToken"]}
    movie_id = await resolve_movie(async_client, login["csrfToken"], 550)
    response = await async_client.post(
        "/v1/logs/",
        headers=headers,
        json={"movieId": movie_id, "dateWatched": "2024-01-01", "watchedWhere": "cinema"},
    )
    assert response.status_code == 201
    async with postgres_engine.begin() as connection:
        await connection.execute(
            text("UPDATE movies SET deleted = true, deleted_at = now() WHERE id = :id"), {"id": movie_id}
        )
    fake_movie_provider.detail_requests.clear()

    history = await async_client.get(f"/v1/logs/{USER['handle']}")
    assert history.status_code == 200
    item = history.json()["logs"][0]
    assert item["movieId"] == movie_id
    assert "tmdbId" not in item
    assert item["movie"] is None
    assert item["posterPath"] == "/poster.jpg"

    for url, body in [
        ("/v1/logs/", {"movieId": movie_id, "dateWatched": "2024-02-01", "watchedWhere": "cinema"}),
        ("/v1/movie-ratings/", {"movieId": movie_id, "rating": 8}),
    ]:
        rejected = await async_client.post(url, headers=headers, json=body)
        assert rejected.status_code == 404
        assert rejected.json()["error_code_name"] == "MOVIE_NOT_FOUND"
    for url in [f"/v1/movies/{movie_id}", f"/v1/movie-ratings/{movie_id}"]:
        hidden = await async_client.get(url, headers={"Accept-Language": "en-US"})
        assert hidden.status_code == 404

    reimport = await async_client.post("/v1/movies/resolve", headers=headers, json={"movieRef": movie_ref_for(550)})
    assert reimport.status_code == 409
    assert reimport.json()["error_code_name"] == "MOVIE_UNAVAILABLE"

    search = await async_client.get(
        "/v1/movies/search", params={"query": "Movie"}, headers={"Accept-Language": "en-US"}
    )
    assert search.json()["results"] == []

    assert fake_movie_provider.detail_requests == []
    assert await _catalog_counts(postgres_engine) == (1, 1)
