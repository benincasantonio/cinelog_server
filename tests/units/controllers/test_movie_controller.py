from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.schemas.movie_api_schemas import (
    MovieDetails,
    MovieGenre,
    MovieProductionCompany,
    MovieProductionCountry,
    MovieResolveRequest,
    MovieSearchResult,
    MovieSearchResultItem,
    MovieSpokenLanguage,
)
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException

MOVIE_ID = uuid4()
CSRF = {"cookies": {"__Host-access_token": "token", "__Host-csrf_token": "csrf"}, "headers": {"X-CSRF-Token": "csrf"}}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"


class TestMovieController:
    """Tests for movie controller endpoints."""

    @patch(
        "app.services.movie_service.MovieService.search_movie",
        new_callable=AsyncMock,
    )
    def test_search_movies_success(self, mock_search, client, override_auth):
        """Test successful movie search."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_search.return_value = MovieSearchResult(
            next_cursor="next",
            results=[
                MovieSearchResultItem(
                    id=MOVIE_ID,
                    title="Fight Club",
                    overview="First rule...",
                    release_date="1999-10-15",
                    poster_path="/path.jpg",
                    vote_average=8.4,
                    original_language="en",
                    original_title="Fight Club",
                    genre_ids=[18],
                    backdrop_path="/backdrop.jpg",
                ),
                MovieSearchResultItem(
                    movie_ref="opaque-ref",
                    title="Fight Club 2",
                    overview="",
                    release_date="",
                    vote_average=0,
                    original_language="en",
                    original_title="Fight Club 2",
                    genre_ids=[],
                ),
            ],
        )

        response = client.get(
            "/v1/movies/search?query=Fight Club&cursor=abc",
            cookies={"__Host-access_token": "token"},
            headers={"Accept-Language": "fr-CA,fr;q=0.9"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert [(item["id"], item["movieRef"]) for item in data["results"]] == [
            (str(MOVIE_ID), None),
            (None, "opaque-ref"),
        ]
        assert data["nextCursor"] == "next"
        assert set(data) == {"results", "nextCursor"}
        mock_search.assert_awaited_once_with(query="Fight Club", locale="fr-FR", cursor="abc")

    def test_search_movies_unauthorized(self, client):
        """Test movie search without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/movies/search?query=Fight Club")
        assert response.status_code == 401

    @patch(
        "app.services.movie_service.MovieService.get_movie_details",
        new_callable=AsyncMock,
    )
    def test_get_movie_details_success(self, mock_get_details, client, override_auth):
        """Test getting movie details."""
        app.dependency_overrides[auth_dependency] = override_auth

        mock_get_details.return_value = MovieDetails(
            id=MOVIE_ID,
            title="Fight Club",
            original_title="Fight Club",
            overview="First rule...",
            release_date="1999-10-15",
            poster_path="/path.jpg",
            backdrop_path="/backdrop.jpg",
            vote_average=8.4,
            vote_count=20000,
            runtime=139,
            budget=63000000,
            revenue=100853753,
            status="Released",
            original_language="en",
            popularity=50.5,
            adult=False,
            genres=[MovieGenre(id=18, name="Drama")],
            production_companies=[
                MovieProductionCompany(
                    id=1,
                    name="20th Century Fox",
                    origin_country="US",
                    logo_path="/logo.jpg",
                )
            ],
            production_countries=[MovieProductionCountry(iso_3166_1="US", name="United States of America")],
            spoken_languages=[MovieSpokenLanguage(iso_639_1="en", name="English", english_name="English")],
        )

        response = client.get(
            f"/v1/movies/{MOVIE_ID}",
            cookies={"__Host-access_token": "token"},
            headers={"Accept-Language": "it-IT"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(MOVIE_ID)
        assert data["title"] == "Fight Club"
        mock_get_details.assert_awaited_once_with(movie_id=MOVIE_ID, locale="it-IT")

    def test_get_movie_details_unauthorized(self, client):
        """Test getting movie details without authentication."""
        app.dependency_overrides = {}
        response = client.get(f"/v1/movies/{MOVIE_ID}")
        assert response.status_code == 401

    @patch(
        "app.services.movie_service.MovieService.search_movie",
        new_callable=AsyncMock,
    )
    def test_search_movies_app_exception(self, mock_search, client, override_auth):
        """Test search movies re-raises AppException."""
        app.dependency_overrides[auth_dependency] = override_auth
        # Use a generic error code that exists
        mock_search.side_effect = AppException(ErrorCodes.MOVIE_NOT_FOUND)

        response = client.get(
            "/v1/movies/search?query=NonExistent",
            cookies={"__Host-access_token": "token"},
            headers={"Accept-Language": "en-US"},
        )

        app.dependency_overrides = {}

        assert response.status_code == ErrorCodes.MOVIE_NOT_FOUND.error_code

    @patch(
        "app.services.movie_service.MovieService.get_movie_details",
        new_callable=AsyncMock,
    )
    def test_get_movie_details_app_exception(self, mock_get_details, client, override_auth):
        """Test get movie details re-raises AppException."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_details.side_effect = AppException(ErrorCodes.MOVIE_NOT_FOUND)

        response = client.get(
            f"/v1/movies/{uuid4()}",
            cookies={"__Host-access_token": "token"},
            headers={"Accept-Language": "en-US"},
        )

        app.dependency_overrides = {}

        assert response.status_code == ErrorCodes.MOVIE_NOT_FOUND.error_code

    @pytest.mark.parametrize("movie_id", ["550", "not-a-uuid"])
    @patch(
        "app.services.movie_service.MovieService.get_movie_details",
        new_callable=AsyncMock,
    )
    def test_get_movie_details_rejects_numeric_and_malformed_ids(
        self, mock_get_details, client, override_auth, movie_id
    ):
        """Removed numeric TMDB paths and malformed UUIDs are validation errors, never provider lookups."""
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.get(
            f"/v1/movies/{movie_id}",
            cookies={"__Host-access_token": "token"},
            headers={"Accept-Language": "en-US"},
        )

        app.dependency_overrides = {}

        assert response.status_code == 422
        mock_get_details.assert_not_awaited()


class TestResolveMovie:
    """Tests for POST /v1/movies/resolve."""

    @patch("app.services.movie_service.MovieService.resolve_movie", new_callable=AsyncMock)
    def test_resolve_returns_movie_id(self, mock_resolve, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_resolve.return_value = MOVIE_ID

        response = client.post("/v1/movies/resolve", json={"movieRef": "opaque-ref"}, **CSRF)

        app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.json() == {"movieId": str(MOVIE_ID)}
        mock_resolve.assert_awaited_once_with("opaque-ref")

    @pytest.mark.parametrize(
        "error",
        [
            ErrorCodes.INVALID_MOVIE_REF,
            ErrorCodes.PROVIDER_MOVIE_NOT_FOUND,
            ErrorCodes.MOVIE_UNAVAILABLE,
            ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE,
            ErrorCodes.MOVIE_PROVIDER_UNAVAILABLE,
        ],
    )
    @patch("app.services.movie_service.MovieService.resolve_movie", new_callable=AsyncMock)
    def test_resolve_maps_service_errors(self, mock_resolve, client, override_auth, error):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_resolve.side_effect = AppException(error)

        response = client.post("/v1/movies/resolve", json={"movieRef": "opaque-ref"}, **CSRF)

        app.dependency_overrides = {}

        assert response.status_code == error.error_code
        assert response.json()["error_code_name"] == error.error_code_name

    @pytest.mark.parametrize(
        "payload",
        [{}, {"movieRef": ""}, {"movieRef": "opaque-ref", "tmdbId": 550}, {"tmdbId": 550}],
    )
    @patch("app.services.movie_service.MovieService.resolve_movie", new_callable=AsyncMock)
    def test_resolve_rejects_invalid_payloads(self, mock_resolve, client, override_auth, payload):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.post("/v1/movies/resolve", json=payload, **CSRF)

        app.dependency_overrides = {}

        assert response.status_code == 422
        mock_resolve.assert_not_awaited()

    def test_resolve_requires_authentication(self, client):
        app.dependency_overrides = {}

        response = client.post("/v1/movies/resolve", json={"movieRef": "opaque-ref"}, **CSRF)

        assert response.status_code == 401

    def test_resolve_requires_csrf(self, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.post(
            "/v1/movies/resolve", json={"movieRef": "opaque-ref"}, cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 403

    def test_resolve_request_schema_forbids_extra_fields(self):
        assert MovieResolveRequest.model_config["extra"] == "forbid"
