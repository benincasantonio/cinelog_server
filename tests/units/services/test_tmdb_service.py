from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import pytest_asyncio

from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult
from app.services.tmdb_cache_service import TMDBCacheService
from app.services.tmdb_service import TMDBService


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SEARCH_PAYLOAD = {
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

DETAILS_PAYLOAD = {
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
        mock_response.json.return_value = SEARCH_PAYLOAD
        mock_response.raise_for_status = Mock()
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
        mock_response.json.return_value = DETAILS_PAYLOAD
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


# ---------------------------------------------------------------------------
# Caching integration tests — TMDBService with a mocked TMDBCacheService
# ---------------------------------------------------------------------------


def _make_mock_cache() -> Mock:
    """Return a Mock whose async methods are AsyncMocks."""
    cache = Mock(spec=TMDBCacheService)
    cache.get_search = AsyncMock(return_value=None)
    cache.set_search = AsyncMock()
    cache.get_details = AsyncMock(return_value=None)
    cache.set_details = AsyncMock()
    return cache


class TestTMDBServiceCaching:
    """TMDBService uses the cache layer correctly for search and details."""

    @pytest_asyncio.fixture
    async def mock_cache(self):
        return _make_mock_cache()

    @pytest_asyncio.fixture
    async def service_with_cache(self, mock_cache):
        service = TMDBService(api_key="test_api_key", cache=mock_cache)
        yield service
        await service.aclose()

    # ------------------------------------------------------------------
    # search_movie
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_search_movie_returns_cached_result_without_calling_api(
        self, mock_cache, service_with_cache
    ):
        """When the cache already holds a result, the TMDB HTTP API must not be called."""
        # Arrange — prime the cache with a pre-built result
        cached_result = TMDBMovieSearchResult(**SEARCH_PAYLOAD)
        mock_cache.get_search = AsyncMock(return_value=cached_result)

        # Act
        with patch(
            "app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock
        ) as mock_http_get:
            result = await service_with_cache.search_movie("Fight Club")

        # Assert
        assert result is cached_result
        mock_http_get.assert_not_awaited()
        mock_cache.get_search.assert_awaited_once_with("Fight Club")

    @pytest.mark.asyncio
    @patch("app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_search_movie_caches_result_on_cache_miss(
        self, mock_http_get, mock_cache, service_with_cache
    ):
        """On a cache miss the service calls the API and stores the result in the cache."""
        # Arrange — cache miss
        mock_cache.get_search = AsyncMock(return_value=None)
        mock_response = Mock()
        mock_response.json.return_value = SEARCH_PAYLOAD
        mock_response.raise_for_status = Mock()
        mock_http_get.return_value = mock_response

        # Act
        result = await service_with_cache.search_movie("Fight Club")

        # Assert — API was called
        mock_http_get.assert_awaited_once()
        # Assert — result is populated correctly
        assert isinstance(result, TMDBMovieSearchResult)
        assert result.results[0].title == "Fight Club"
        # Assert — result was written back to the cache
        mock_cache.set_search.assert_awaited_once_with("Fight Club", result)

    # ------------------------------------------------------------------
    # get_movie_details
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_movie_details_returns_cached_result_without_calling_api(
        self, mock_cache, service_with_cache
    ):
        """When the cache already holds details, the TMDB HTTP API must not be called."""
        # Arrange
        cached_details = TMDBMovieDetails(**DETAILS_PAYLOAD)
        mock_cache.get_details = AsyncMock(return_value=cached_details)

        # Act
        with patch(
            "app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock
        ) as mock_http_get:
            result = await service_with_cache.get_movie_details(550)

        # Assert
        assert result is cached_details
        mock_http_get.assert_not_awaited()
        mock_cache.get_details.assert_awaited_once_with(550)

    @pytest.mark.asyncio
    @patch("app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_get_movie_details_caches_result_on_cache_miss(
        self, mock_http_get, mock_cache, service_with_cache
    ):
        """On a cache miss the service calls the API and stores the details in the cache."""
        # Arrange — cache miss
        mock_cache.get_details = AsyncMock(return_value=None)
        mock_response = Mock()
        mock_response.json.return_value = DETAILS_PAYLOAD
        mock_response.raise_for_status = Mock()
        mock_http_get.return_value = mock_response

        # Act
        result = await service_with_cache.get_movie_details(550)

        # Assert — API was called
        mock_http_get.assert_awaited_once()
        # Assert — result is populated correctly
        assert isinstance(result, TMDBMovieDetails)
        assert result.id == 550
        assert result.runtime == 139
        # Assert — result was written back to the cache
        mock_cache.set_details.assert_awaited_once_with(550, result)

    # ------------------------------------------------------------------
    # raise_for_status propagation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("app.services.tmdb_service.httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_search_movie_raises_on_bad_status(
        self, mock_http_get, mock_cache, service_with_cache
    ):
        """search_movie propagates an HTTP error from raise_for_status to the caller."""
        # Arrange
        request = httpx.Request("GET", "https://api.themoviedb.org/3/search/movie")
        response = httpx.Response(500, request=request)
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=request,
            response=response,
        )
        mock_http_get.return_value = mock_response

        # Act / Assert
        with pytest.raises(httpx.HTTPStatusError):
            await service_with_cache.search_movie("Fight Club")

        # The error must surface before any cache write occurs
        mock_cache.set_search.assert_not_awaited()
