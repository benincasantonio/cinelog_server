from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import pytest_asyncio

from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult
from app.services.tmdb_service import TMDBService


class TestTMDBService:
    """Tests for TMDBService."""

    @pytest_asyncio.fixture
    async def tmdb_service(self):
        service = TMDBService(api_key="test_api_key")
        yield service
        await service.aclose()

    @pytest.mark.asyncio
    @patch("app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_search_movie(self, mock_get, tmdb_service):
        """Test searching for a movie."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "page": 1,
            "results": [
                {
                    "id": 550,
                    "title": "Fight Club",
                    "overview": "An insomniac office worker...",
                    "release_date": "1999-10-15",
                    "poster_path": "/poster.jpg",
                    "vote_average": 8.4,
                    "genre_ids": [18, 53],
                    "original_language": "en",
                    "original_title": "Fight Club",
                    "adult": False,
                    "backdrop_path": "/backdrop.jpg",
                    "popularity": 50.5,
                    "video": False,
                    "vote_count": 20000,
                }
            ],
            "total_pages": 1,
            "total_results": 1,
        }
        mock_get.return_value = mock_response

        result = await tmdb_service.search_movie("Fight Club")

        assert isinstance(result, TMDBMovieSearchResult)
        assert result.total_results == 1
        assert len(result.results) == 1
        assert result.results[0].title == "Fight Club"
        mock_get.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_get_movie_details(self, mock_get, tmdb_service):
        """Test getting full movie details."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 550,
            "title": "Fight Club",
            "original_title": "Fight Club",
            "overview": "An insomniac office worker...",
            "release_date": "1999-10-15",
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "vote_average": 8.4,
            "vote_count": 20000,
            "runtime": 139,
            "budget": 63000000,
            "revenue": 100853753,
            "status": "Released",
            "tagline": "Mischief. Mayhem. Soap.",
            "homepage": "https://www.foxmovies.com/movies/fight-club",
            "imdb_id": "tt0137523",
            "original_language": "en",
            "popularity": 50.5,
            "adult": False,
            "genres": [{"id": 18, "name": "Drama"}],
            "production_companies": [],
            "production_countries": [],
            "spoken_languages": [],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = await tmdb_service.get_movie_details(550)

        assert isinstance(result, TMDBMovieDetails)
        assert result.id == 550
        assert result.title == "Fight Club"
        assert result.runtime == 139
        mock_get.assert_awaited_once()
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_get_movie_details_not_found(self, mock_get, tmdb_service):
        """Test getting movie details when movie doesn't exist."""
        request = httpx.Request("GET", "https://api.themoviedb.org/3/movie/999999999")
        response = httpx.Response(404, request=request)

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=request,
            response=response,
        )
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await tmdb_service.get_movie_details(999999999)
