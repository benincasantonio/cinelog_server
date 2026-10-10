from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.schemas.movie_provider_schemas import MovieDetailsQuery
from app.services.movie_service import MovieService
from tests.fakes.movie_provider import movie_metadata


class TestMovieService:
    """Tests for MovieService."""

    @pytest.fixture
    def mock_movie_repository(self):
        return AsyncMock()

    @pytest.fixture
    def mock_provider(self):
        return AsyncMock()

    @pytest.fixture
    def movie_service(self, mock_movie_repository, mock_provider):
        return MovieService(movie_repository=mock_movie_repository, provider=mock_provider)

    @pytest.mark.asyncio
    async def test_get_movie_by_id(self, movie_service, mock_movie_repository):
        """Test getting a movie by ID."""
        mock_movie = Mock()
        movie_id = uuid4()
        mock_movie.id = movie_id
        mock_movie.title = "Test Movie"
        mock_movie_repository.find_movie_by_id.return_value = mock_movie

        result = await movie_service.get_movie_by_id(movie_id)

        assert result == mock_movie
        mock_movie_repository.find_movie_by_id.assert_awaited_once_with(movie_id)

    @pytest.mark.asyncio
    async def test_get_movie_by_id_not_found(self, movie_service, mock_movie_repository):
        """Test getting a movie by ID when not found."""
        mock_movie_repository.find_movie_by_id.return_value = None

        result = await movie_service.get_movie_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_movie_by_tmdb_id(self, movie_service, mock_movie_repository):
        """Test getting a movie by TMDB ID."""
        mock_movie = Mock()
        mock_movie.id = uuid4()
        mock_movie.tmdb_id = 550
        mock_movie_repository.find_movie_by_tmdb_id.return_value = mock_movie

        result = await movie_service.get_movie_by_tmdb_id(550)

        assert result == mock_movie
        mock_movie_repository.find_movie_by_tmdb_id.assert_awaited_once_with(550)

    @pytest.mark.asyncio
    async def test_find_or_create_movie_exists(self, movie_service, mock_movie_repository, mock_provider):
        """Test find_or_create when movie already exists."""
        mock_movie = Mock()
        mock_movie.id = uuid4()
        mock_movie_repository.find_movie_by_tmdb_id.return_value = mock_movie

        result = await movie_service.find_or_create_movie(550)

        assert result == mock_movie
        # Should not call TMDB API since movie exists
        mock_provider.get_movie_details.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_find_or_create_movie_creates_new(self, movie_service, mock_movie_repository, mock_provider):
        """Test find_or_create when movie doesn't exist."""
        mock_movie_repository.find_movie_by_tmdb_id.return_value = None

        metadata = movie_metadata()
        mock_provider.get_movie_details.return_value = metadata

        mock_new_movie = Mock()
        mock_movie_repository.create_movie.return_value = mock_new_movie

        result = await movie_service.find_or_create_movie(550)

        assert result == mock_new_movie
        mock_provider.get_movie_details.assert_awaited_once_with(MovieDetailsQuery(external_id="550", locale="en-US"))
        data = mock_movie_repository.create_movie.await_args.args[0]
        assert data.source == metadata.source
        assert data.title == metadata.localized.title
        assert data.observed_at == metadata.observed_at
        assert data.source_payload == metadata.source_payload
        assert "canonical_movie_id" not in type(data).model_fields


async def test_detail_wire_contract_uses_neutral_metadata():
    from tests.fakes.movie_provider import FakeMovieProvider

    provider = FakeMovieProvider()
    service = MovieService(AsyncMock(), provider)
    response = await service.get_movie_details(550, "it-IT")
    assert response.model_dump(by_alias=True) == {
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
    assert provider.detail_requests == [MovieDetailsQuery(external_id="550", locale="it-IT")]


async def test_search_wire_contract_and_unknown_date():
    from app.schemas.movie_provider_schemas import MovieSearchQuery
    from tests.fakes.movie_provider import FakeMovieProvider

    request = MovieSearchQuery(query="film", locale="fr-FR")
    result = await FakeMovieProvider().search_movie(request)
    result.results[0].common.release_date = None
    result.page, result.total_pages, result.total_results = 2, 3, 42
    provider = AsyncMock()
    provider.search_movie.return_value = result
    response = await MovieService(AsyncMock(), provider).search_movie("film", "fr-FR")
    assert response.model_dump(by_alias=True) == {
        "page": 2,
        "totalResults": 42,
        "totalPages": 3,
        "results": [
            {
                "id": 550,
                "title": "Movie 550",
                "overview": "Mocked movie details",
                "releaseDate": "",
                "posterPath": "/poster.jpg",
                "voteAverage": 7.5,
                "backdropPath": "/backdrop.jpg",
                "genreIds": [],
                "originalLanguage": "en",
                "originalTitle": "Movie 550",
            }
        ],
    }
    provider.search_movie.assert_awaited_once_with(request)


async def test_unknown_detail_date_preserves_public_empty_string():
    data = movie_metadata()
    data.common.release_date = None
    provider = AsyncMock()
    provider.get_movie_details.return_value = data
    assert (await MovieService(AsyncMock(), provider).get_movie_details(550)).release_date == ""


async def test_provider_canonical_id_cannot_be_imported():
    data = movie_metadata()
    data.canonical_movie_id = uuid4()
    repository, provider = AsyncMock(), AsyncMock()
    repository.find_movie_by_tmdb_id.return_value = None
    provider.get_movie_details.return_value = data
    await MovieService(repository, provider).find_or_create_movie(550)
    imported = repository.create_movie.await_args.args[0]
    assert "canonical_movie_id" not in imported.model_dump()
    assert "id" not in imported.model_dump()
