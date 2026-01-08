import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app import app
from app.schemas.tmdb_schemas import TMDBMovieSearchResult, TMDBMovieDetails


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_auth_token():
    return "Bearer mock_valid_token"


class TestMovieController:
    """Tests for movie controller endpoints."""

    @patch('app.controllers.movie_controller.tmdb_service.search_movie')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_search_movies_success(
        self,
        mock_verify_token,
        mock_search,
        client,
        mock_auth_token
    ):
        """Test successful movie search."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        
        mock_search.return_value = TMDBMovieSearchResult(
            page=1,
            results=[],
            total_pages=1,
            total_results=0
        )

        response = client.get(
            "/v1/movies/search?query=Fight+Club",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        mock_search.assert_called_once_with(query="Fight Club")

    def test_search_movies_unauthorized(self, client):
        """Test movie search without authentication."""
        response = client.get("/v1/movies/search?query=Fight+Club")
        assert response.status_code == 401

    @patch('app.controllers.movie_controller.tmdb_service.get_movie_details')
    @patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token')
    def test_get_movie_details_success(
        self,
        mock_verify_token,
        mock_get_details,
        client,
        mock_auth_token
    ):
        """Test getting movie details."""
        mock_verify_token.return_value = {"uid": "firebase_uid"}
        
        mock_get_details.return_value = TMDBMovieDetails(
            id=550,
            title="Fight Club",
            originalTitle="Fight Club",
            overview="An insomniac office worker...",
            releaseDate="1999-10-15",
            posterPath="/poster.jpg",
            backdropPath="/backdrop.jpg",
            voteAverage=8.4,
            voteCount=20000,
            runtime=139,
            budget=63000000,
            revenue=100853753,
            status="Released",
            originalLanguage="en",
            popularity=50.5,
            adult=False,
            genres=[],
            productionCompanies=[],
            productionCountries=[],
            spokenLanguages=[]
        )

        response = client.get(
            "/v1/movies/550",
            headers={"Authorization": mock_auth_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 550
        assert data["title"] == "Fight Club"

    def test_get_movie_details_unauthorized(self, client):
        """Test getting movie details without authentication."""
        response = client.get("/v1/movies/550")
        assert response.status_code == 401
