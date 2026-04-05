from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult
from app.services.tmdb_cache_service import (
    TMDB_DETAILS_CACHE_TTL,
    TMDB_SEARCH_CACHE_TTL,
    TMDBCacheService,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SEARCH_RESULT_DATA = {
    "page": 1,
    "total_results": 1,
    "total_pages": 1,
    "results": [
        {
            "id": 550,
            "title": "Fight Club",
            "overview": "An insomniac office worker...",
            "release_date": "1999-10-15",
            "poster_path": "/poster.jpg",
            "vote_average": 8.4,
            "backdrop_path": "/backdrop.jpg",
            "genre_ids": [18, 53],
            "original_language": "en",
            "original_title": "Fight Club",
        }
    ],
}

DETAILS_DATA = {
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mock_cache():
    """A fully-functional AsyncMock standing in for CacheService."""
    return AsyncMock()


@pytest_asyncio.fixture
async def cache_service(mock_cache):
    """TMDBCacheService with a pre-resolved mock CacheService injected."""
    svc = TMDBCacheService()
    # Bypass the lazy-resolved property so no real CacheService.get_instance() call happens.
    svc._cache_instance = mock_cache
    svc._cache_resolved = True
    return svc


@pytest_asyncio.fixture
async def unavailable_cache_service():
    """TMDBCacheService where the underlying CacheService could not be initialised."""
    svc = TMDBCacheService()
    svc._cache_instance = None
    svc._cache_resolved = True
    return svc


# ---------------------------------------------------------------------------
# Key-building tests (pure, no I/O)
# ---------------------------------------------------------------------------


class TestBuildKeys:
    """TMDBCacheService static key builders produce the expected patterns."""

    def test_build_search_key_lowercases_query(self):
        # Arrange
        query = "Fight Club"

        # Act
        key = TMDBCacheService.build_search_key(query)

        # Assert
        assert key == "cinelog:tmdb:search:fight club"

    def test_build_search_key_strips_whitespace(self):
        # Arrange
        query = "  Fight Club  "

        # Act
        key = TMDBCacheService.build_search_key(query)

        # Assert
        assert key == "cinelog:tmdb:search:fight club"

    def test_build_search_key_normalizes_mixed_case_and_whitespace(self):
        # Arrange
        query = "  THE GODFATHER  "

        # Act
        key = TMDBCacheService.build_search_key(query)

        # Assert
        assert key == "cinelog:tmdb:search:the godfather"

    def test_build_details_key(self):
        # Arrange
        tmdb_id = 550

        # Act
        key = TMDBCacheService.build_details_key(tmdb_id)

        # Assert
        assert key == "cinelog:tmdb:details:550"

    def test_build_details_key_uses_numeric_id(self):
        # Arrange
        tmdb_id = 11

        # Act
        key = TMDBCacheService.build_details_key(tmdb_id)

        # Assert
        assert key == "cinelog:tmdb:details:11"


# ---------------------------------------------------------------------------
# Search cache tests
# ---------------------------------------------------------------------------


class TestGetSearch:
    """get_search returns a deserialised TMDBMovieSearchResult on a hit, None on a miss."""

    @pytest.mark.asyncio
    async def test_get_search_cache_hit(self, cache_service, mock_cache):
        # Arrange — the backing cache holds the serialised result
        mock_cache.get = AsyncMock(return_value=SEARCH_RESULT_DATA)

        # Act
        result = await cache_service.get_search("Fight Club")

        # Assert
        assert isinstance(result, TMDBMovieSearchResult)
        assert result.total_results == 1
        assert result.results[0].title == "Fight Club"
        mock_cache.get.assert_awaited_once_with("cinelog:tmdb:search:fight club")

    @pytest.mark.asyncio
    async def test_get_search_cache_miss(self, cache_service, mock_cache):
        # Arrange — cache returns nothing for this key
        mock_cache.get = AsyncMock(return_value=None)

        # Act
        result = await cache_service.get_search("unknown movie")

        # Assert
        assert result is None
        mock_cache.get.assert_awaited_once_with("cinelog:tmdb:search:unknown movie")


class TestSetSearch:
    """set_search serialises and stores the result with the configured TTL."""

    @pytest.mark.asyncio
    async def test_set_search_stores_result_with_correct_ttl(
        self, cache_service, mock_cache
    ):
        # Arrange
        mock_cache.set = AsyncMock()
        search_result = TMDBMovieSearchResult(**SEARCH_RESULT_DATA)
        expected_key = "cinelog:tmdb:search:fight club"

        # Act
        await cache_service.set_search("Fight Club", search_result)

        # Assert
        mock_cache.set.assert_awaited_once_with(
            expected_key,
            search_result.model_dump(mode="json"),
            ttl=TMDB_SEARCH_CACHE_TTL,
        )

    @pytest.mark.asyncio
    async def test_set_search_normalizes_query_key(self, cache_service, mock_cache):
        # Arrange — whitespace and case in the query must not leak into the cache key
        mock_cache.set = AsyncMock()
        search_result = TMDBMovieSearchResult(**SEARCH_RESULT_DATA)

        # Act
        await cache_service.set_search("  Fight Club  ", search_result)

        # Assert — key is normalised regardless of raw query
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "cinelog:tmdb:search:fight club"


# ---------------------------------------------------------------------------
# Details cache tests
# ---------------------------------------------------------------------------


class TestGetDetails:
    """get_details returns a deserialised TMDBMovieDetails on a hit, None on a miss."""

    @pytest.mark.asyncio
    async def test_get_details_cache_hit(self, cache_service, mock_cache):
        # Arrange
        mock_cache.get = AsyncMock(return_value=DETAILS_DATA)

        # Act
        result = await cache_service.get_details(550)

        # Assert
        assert isinstance(result, TMDBMovieDetails)
        assert result.id == 550
        assert result.title == "Fight Club"
        assert result.runtime == 139
        mock_cache.get.assert_awaited_once_with("cinelog:tmdb:details:550")

    @pytest.mark.asyncio
    async def test_get_details_cache_miss(self, cache_service, mock_cache):
        # Arrange
        mock_cache.get = AsyncMock(return_value=None)

        # Act
        result = await cache_service.get_details(999999)

        # Assert
        assert result is None
        mock_cache.get.assert_awaited_once_with("cinelog:tmdb:details:999999")


class TestSetDetails:
    """set_details serialises and stores movie details with the configured TTL."""

    @pytest.mark.asyncio
    async def test_set_details_stores_result_with_correct_ttl(
        self, cache_service, mock_cache
    ):
        # Arrange
        mock_cache.set = AsyncMock()
        details = TMDBMovieDetails(**DETAILS_DATA)
        expected_key = "cinelog:tmdb:details:550"

        # Act
        await cache_service.set_details(550, details)

        # Assert
        mock_cache.set.assert_awaited_once_with(
            expected_key,
            details.model_dump(mode="json"),
            ttl=TMDB_DETAILS_CACHE_TTL,
        )


# ---------------------------------------------------------------------------
# Cache unavailable — all methods degrade gracefully
# ---------------------------------------------------------------------------


class TestCacheUnavailable:
    """When CacheService was never initialised, all methods are safe no-ops."""

    @pytest.mark.asyncio
    async def test_get_search_returns_none(self, unavailable_cache_service):
        # Act
        result = await unavailable_cache_service.get_search("Fight Club")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_set_search_is_noop(self, unavailable_cache_service):
        # Arrange
        search_result = TMDBMovieSearchResult(**SEARCH_RESULT_DATA)

        # Act — must not raise
        await unavailable_cache_service.set_search("Fight Club", search_result)

    @pytest.mark.asyncio
    async def test_get_details_returns_none(self, unavailable_cache_service):
        # Act
        result = await unavailable_cache_service.get_details(550)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_set_details_is_noop(self, unavailable_cache_service):
        # Arrange
        details = TMDBMovieDetails(**DETAILS_DATA)

        # Act — must not raise
        await unavailable_cache_service.set_details(550, details)

    @pytest.mark.asyncio
    async def test_cache_resolved_lazily_when_not_initialized(self):
        """
        TMDBCacheService resolves the CacheService singleton lazily.
        When the singleton is absent a RuntimeError is caught internally and
        _cache_instance is set to None — the service stays usable.
        """
        # Arrange — ensure no singleton is registered
        from app.services.cache_service import CacheService

        CacheService._singleton = None

        svc = TMDBCacheService()  # _cache_resolved starts False

        # Act
        result = await svc.get_search("Fight Club")

        # Assert
        assert result is None
        assert svc._cache_instance is None
        assert svc._cache_resolved is True
