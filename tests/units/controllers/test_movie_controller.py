import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app import app
from app.schemas.tmdb_schemas import (
    TMDBMovieSearchResult, 
    TMDBMovieDetails,
    TMDBMovieSearchResultItem,
    TMDBGenre,
    TMDBProductionCompany,
    TMDBProductionCountry,
    TMDBSpokenLanguage
)
from app.dependencies.auth_dependency import auth_dependency
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    """Mock successful authentication."""
    return lambda: "user123"


class TestMovieController:
    """Tests for movie controller endpoints."""

    @patch('app.controllers.movie_controller.tmdb_service.search_movie')
    def test_search_movies_success(
        self,
        mock_search,
        client,
        override_auth
    ):
        """Test successful movie search."""
        app.dependency_overrides[auth_dependency] = override_auth
        
        mock_search.return_value = TMDBMovieSearchResult(
            page=1,
            total_results=1,
            total_pages=1,
            results=[
                TMDBMovieSearchResultItem(
                    id=550,
                    title="Fight Club",
                    overview="First rule...",
                    release_date="1999-10-15",
                    poster_path="/path.jpg",
                    vote_average=8.4,
                    original_language="en",
                    original_title="Fight Club",
                    genre_ids=[18],
                    backdrop_path="/backdrop.jpg",
                    popularity=50.5,
                    vote_count=20000,
                    video=False,
                    adult=False
                )
            ]
        )

        response = client.get(
            "/v1/movies/search?query=Fight Club",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Fight Club"
        mock_search.assert_called_once_with(query="Fight Club")

    def test_search_movies_unauthorized(self, client):
        """Test movie search without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/movies/search?query=Fight Club")
        assert response.status_code == 401

    @patch('app.controllers.movie_controller.tmdb_service.get_movie_details')
    def test_get_movie_details_success(
        self,
        mock_get_details,
        client,
        override_auth
    ):
        """Test getting movie details."""
        app.dependency_overrides[auth_dependency] = override_auth
        
        mock_get_details.return_value = TMDBMovieDetails(
            id=550,
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
            genres=[TMDBGenre(id=18, name="Drama")],
            production_companies=[
                TMDBProductionCompany(
                    id=1, 
                    name="20th Century Fox", 
                    origin_country="US",
                    logo_path="/logo.jpg"
                )
            ],
            production_countries=[
                TMDBProductionCountry(iso_3166_1="US", name="United States of America")
            ],
            spoken_languages=[
                TMDBSpokenLanguage(iso_639_1="en", name="English", english_name="English")
            ]
        )

        response = client.get(
            "/v1/movies/550",
            cookies={"__Host-access_token": "token"}
        )

        app.dependency_overrides = {}

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Fight Club"
        mock_get_details.assert_called_once_with(tmdb_id=550)

    def test_get_movie_details_unauthorized(self, client):
        """Test getting movie details without authentication."""
        app.dependency_overrides = {}
        response = client.get("/v1/movies/550")
        assert response.status_code == 401

    @patch('app.controllers.movie_controller.tmdb_service.search_movie')
    def test_search_movies_app_exception(
        self,
        mock_search,
        client,
        override_auth
    ):
        """Test search movies re-raises AppException."""
        app.dependency_overrides[auth_dependency] = override_auth
        # Use a generic error code that exists
        mock_search.side_effect = AppException(ErrorCodes.MOVIE_NOT_FOUND)

        response = client.get(
            "/v1/movies/search?query=NonExistent",
            cookies={"__Host-access_token": "token"}
        )
        
        app.dependency_overrides = {}

        assert response.status_code == ErrorCodes.MOVIE_NOT_FOUND.error_code

    @patch('app.controllers.movie_controller.tmdb_service.get_movie_details')
    def test_get_movie_details_app_exception(
        self,
        mock_get_details,
        client,
        override_auth
    ):
        """Test get movie details re-raises AppException."""
        app.dependency_overrides[auth_dependency] = override_auth
        mock_get_details.side_effect = AppException(ErrorCodes.MOVIE_NOT_FOUND)

        response = client.get(
            "/v1/movies/999999",
            cookies={"__Host-access_token": "token"}
        )
        
        app.dependency_overrides = {}

        assert response.status_code == ErrorCodes.MOVIE_NOT_FOUND.error_code
