from unittest.mock import AsyncMock

import pytest

from app.repository.movie_repository import MovieRepository
from app.schemas.movie_provider_schemas import MovieDetailsQuery, MovieSearchQuery
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException
from tests.e2e.conftest import register_and_login
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


async def test_movie_search_detail_import_and_repeat_writes(async_client, fake_movie_provider):
    login = await register_and_login(async_client, USER)
    search = await async_client.get(
        "/v1/movies/search", params={"query": "Movie"}, headers={"Accept-Language": "fr-FR"}
    )
    assert search.status_code == 200
    assert search.json() == {
        "page": 1,
        "totalResults": 1,
        "totalPages": 1,
        "results": [
            {
                "id": 550,
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
        ],
    }
    assert fake_movie_provider.search_requests == [MovieSearchQuery(query="Movie", locale="fr-FR")]
    detail = await async_client.get("/v1/movies/550", headers={"Accept-Language": "it-IT"})
    assert detail.status_code == 200
    assert detail.json() == {
        "id": 550,
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
    fake_movie_provider.detail_requests.clear()
    headers = {"X-CSRF-Token": login["csrfToken"]}
    ids = []
    for _ in range(2):
        logged = await async_client.post(
            "/v1/logs/", headers=headers, json={"tmdbId": 550, "dateWatched": "2024-01-01", "watchedWhere": "cinema"}
        )
        assert logged.status_code == 201
        ids.append(logged.json()["movieId"])
    assert ids[0] == ids[1]
    assert fake_movie_provider.detail_requests == [MovieDetailsQuery(external_id="550", locale="en-US")]
    stored = await MovieRepository().find_movie_by_tmdb_id(550)
    assert str(stored.id) == ids[0]
    assert stored.tmdb_last_synced_at == OBSERVED_AT
    assert stored.tmdb_payload == {"fixture": "opaque snapshot"}


async def test_second_user_log_reuses_movie_imported_by_first_user(async_client, fake_movie_provider):
    users = [
        {**USER, "email": f"provider-{suffix}@example.com", "handle": f"movieprovider{suffix}"} for suffix in ("a", "b")
    ]
    movie_ids = []
    log_ids = []
    for user in users:
        # Logging in replaces the shared client's auth cookies, so each log is written by its own user.
        login = await register_and_login(async_client, user)
        logged = await async_client.post(
            "/v1/logs/",
            headers={"X-CSRF-Token": login["csrfToken"]},
            json={"tmdbId": 550, "dateWatched": "2024-01-01", "watchedWhere": "cinema"},
        )
        assert logged.status_code == 201
        movie_ids.append(logged.json()["movieId"])
        log_ids.append(logged.json()["id"])

    assert movie_ids[0] == movie_ids[1]
    assert log_ids[0] != log_ids[1]
    # Only the first user's log imports the movie; the second reuses the stored row.
    assert fake_movie_provider.detail_requests == [MovieDetailsQuery(external_id="550", locale="en-US")]
    stored = await MovieRepository().find_movie_by_tmdb_id(550)
    assert str(stored.id) == movie_ids[0]

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
    await register_and_login(async_client, USER)
    fake_movie_provider.get_movie_details = AsyncMock(side_effect=AppException(error))
    response = await async_client.get("/v1/movies/550", headers={"Accept-Language": "en-US"})
    assert response.status_code == error.error_code
    assert response.json() == {
        "error_code_name": error.error_code_name,
        "error_code": error.error_code,
        "error_message": error.error_message,
        "error_description": error.error_description,
    }
