from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.movie_provider_mapping_model import MovieProviderMapping
from app.repository.movie_repository_protocol import MovieIdentityUnavailableError
from app.schemas.movie_provider_schemas import (
    MovieDetailsQuery,
    MovieSearchQuery,
    MovieSearchResultDTO,
    MovieSourceReferenceDTO,
)
from app.services.movie_service import MovieService
from app.utils.cursor_pagination_utils import decode_movie_search_cursor, encode_movie_search_cursor
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException
from app.utils.movie_ref_utils import decode_movie_ref, encode_movie_ref
from tests.fakes.movie_provider import FakeMovieProvider, movie_metadata

TMDB_550 = MovieSourceReferenceDTO(source="tmdb", external_id="550")


def _catalog_movie(external_id: str = "550", *, deleted: bool = False) -> Mock:
    movie = Mock(deleted=deleted)
    movie.id = uuid4()
    movie.providers = [MovieProviderMapping(provider="tmdb", external_id=external_id)]
    return movie


async def _search_page(
    external_ids: list[str], *, page: int = 1, total_pages: int = 1, locale: str = "en-US"
) -> MovieSearchResultDTO:
    result = await FakeMovieProvider().search_movie(MovieSearchQuery(query="film", locale=locale))
    template = result.results[0]
    result.results = [
        template.model_copy(update={"source": MovieSourceReferenceDTO(source="tmdb", external_id=external_id)})
        for external_id in external_ids
    ]
    result.page, result.total_pages, result.total_results = page, total_pages, total_pages * 20
    return result


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
        mock_movie = Mock(deleted=False)
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
    async def test_get_active_movie_returns_catalog_movie(self, movie_service, mock_movie_repository):
        movie = _catalog_movie()
        mock_movie_repository.find_movie_by_id.return_value = movie

        assert await movie_service.get_active_movie(movie.id) is movie
        mock_movie_repository.find_movie_by_id.assert_awaited_once_with(movie.id)

    @pytest.mark.asyncio
    async def test_get_active_movie_unknown_or_deleted_is_not_found(self, movie_service, mock_movie_repository):
        # The repository hides soft-deleted movies, so both cases arrive as None.
        mock_movie_repository.find_movie_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            await movie_service.get_active_movie(uuid4())

        assert exc_info.value.error == ErrorCodes.MOVIE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_resolve_returns_existing_movie_without_refreshing(
        self, movie_service, mock_movie_repository, mock_provider
    ):
        movie = _catalog_movie()
        mock_movie_repository.find_movie_by_provider.return_value = movie

        result = await movie_service.resolve_movie(encode_movie_ref(TMDB_550))

        assert result == movie.id
        mock_movie_repository.find_movie_by_provider.assert_awaited_once_with(TMDB_550, include_deleted=True)
        mock_provider.get_movie_details.assert_not_awaited()
        mock_movie_repository.create_movie.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolve_imports_first_selection(self, movie_service, mock_movie_repository, mock_provider):
        mock_movie_repository.find_movie_by_provider.return_value = None
        metadata = movie_metadata()
        mock_provider.get_movie_details.return_value = metadata
        imported = _catalog_movie()
        mock_movie_repository.create_movie.return_value = imported

        result = await movie_service.resolve_movie(encode_movie_ref(TMDB_550))

        assert result == imported.id
        mock_provider.get_movie_details.assert_awaited_once_with(MovieDetailsQuery(external_id="550", locale="en-US"))
        data = mock_movie_repository.create_movie.await_args.args[0]
        assert data.source == metadata.source
        assert data.title == metadata.localized.title
        assert data.observed_at == metadata.observed_at
        assert data.source_payload == metadata.source_payload
        assert "canonical_movie_id" not in type(data).model_fields

    @pytest.mark.asyncio
    async def test_resolve_maps_concurrently_deleted_identity_to_app_error(
        self, movie_service, mock_movie_repository, mock_provider
    ):
        """A soft-deleted source identity surfaces as MOVIE_UNAVAILABLE, not an unhandled error."""
        mock_movie_repository.find_movie_by_provider.return_value = None
        mock_provider.get_movie_details.return_value = movie_metadata()
        mock_movie_repository.create_movie.side_effect = MovieIdentityUnavailableError("tmdb:550")

        with pytest.raises(AppException) as exc_info:
            await movie_service.resolve_movie(encode_movie_ref(TMDB_550))

        assert exc_info.value.error == ErrorCodes.MOVIE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_resolve_provider_failure_creates_nothing(self, movie_service, mock_movie_repository, mock_provider):
        mock_movie_repository.find_movie_by_provider.return_value = None
        mock_provider.get_movie_details.side_effect = AppException(ErrorCodes.PROVIDER_MOVIE_NOT_FOUND)

        with pytest.raises(AppException) as exc_info:
            await movie_service.resolve_movie(encode_movie_ref(TMDB_550))

        assert exc_info.value.error == ErrorCodes.PROVIDER_MOVIE_NOT_FOUND
        mock_movie_repository.create_movie.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("movie_ref", ["", "tmdb:550", "550", "not.a-ref"])
    async def test_resolve_rejects_invalid_reference_without_io(
        self, movie_service, mock_movie_repository, mock_provider, movie_ref
    ):
        with pytest.raises(AppException) as exc_info:
            await movie_service.resolve_movie(movie_ref)

        assert exc_info.value.error == ErrorCodes.INVALID_MOVIE_REF
        mock_movie_repository.find_movie_by_provider.assert_not_awaited()
        mock_provider.get_movie_details.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_movie_details_unknown_movie_skips_provider(
        self, movie_service, mock_movie_repository, mock_provider
    ):
        mock_movie_repository.find_movie_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            await movie_service.get_movie_details(uuid4())

        assert exc_info.value.error == ErrorCodes.MOVIE_NOT_FOUND
        mock_provider.get_movie_details.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_movie_details_without_tmdb_mapping_is_not_found(
        self, movie_service, mock_movie_repository, mock_provider
    ):
        movie = _catalog_movie()
        movie.providers = []
        mock_movie_repository.find_movie_by_id.return_value = movie

        with pytest.raises(AppException) as exc_info:
            await movie_service.get_movie_details(movie.id)

        assert exc_info.value.error == ErrorCodes.MOVIE_NOT_FOUND
        mock_provider.get_movie_details.assert_not_awaited()


async def test_detail_wire_contract_uses_canonical_id_and_neutral_metadata():
    provider = FakeMovieProvider()
    repository = AsyncMock()
    movie = _catalog_movie()
    repository.find_movie_by_id.return_value = movie
    response = await MovieService(repository, provider).get_movie_details(movie.id, "it-IT")
    assert response.model_dump(by_alias=True) == {
        "id": movie.id,
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
    result = await _search_page(["550"], locale="fr-FR")
    result.results[0].common.release_date = None
    provider = AsyncMock()
    provider.search_movie.return_value = result
    repository = AsyncMock()
    repository.find_movies_by_external_ids.return_value = {}

    response = await MovieService(repository, provider).search_movie("film", "fr-FR")

    assert response.model_dump(by_alias=True) == {
        "results": [
            {
                "id": None,
                "movieRef": encode_movie_ref(TMDB_550),
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
        "nextCursor": None,
    }
    provider.search_movie.assert_awaited_once_with(MovieSearchQuery(query="film", locale="fr-FR", page=1))


async def test_search_names_catalog_films_by_uuid_and_omits_deleted_ones_without_writes():
    known, deleted = _catalog_movie("550"), _catalog_movie("551", deleted=True)
    provider = AsyncMock()
    provider.search_movie.return_value = await _search_page(["550", "551", "552"])
    repository = AsyncMock()
    repository.find_movies_by_external_ids.return_value = {"550": known, "551": deleted}

    response = await MovieService(repository, provider).search_movie("film")

    assert [(item.id, item.movie_ref) for item in response.results] == [
        (known.id, None),
        (None, encode_movie_ref(MovieSourceReferenceDTO(source="tmdb", external_id="552"))),
    ]
    repository.find_movies_by_external_ids.assert_awaited_once_with("tmdb", ["550", "551", "552"])
    repository.create_movie.assert_not_awaited()
    provider.get_movie_details.assert_not_awaited()


async def test_search_cursor_requests_the_signed_page_and_issues_the_next_one():
    provider = AsyncMock()
    provider.search_movie.return_value = await _search_page(["550"], page=2, total_pages=3, locale="it-IT")
    repository = AsyncMock()
    repository.find_movies_by_external_ids.return_value = {}
    cursor = encode_movie_search_cursor(2, query="film", locale="it-IT")

    response = await MovieService(repository, provider).search_movie("film", "it-IT", cursor)

    provider.search_movie.assert_awaited_once_with(MovieSearchQuery(query="film", locale="it-IT", page=2))
    assert response.next_cursor is not None
    assert decode_movie_search_cursor(response.next_cursor, query="film", locale="it-IT") == 3


async def test_search_page_with_only_deleted_films_is_empty_but_continues():
    provider = AsyncMock()
    provider.search_movie.return_value = await _search_page(["551"], total_pages=2)
    repository = AsyncMock()
    repository.find_movies_by_external_ids.return_value = {"551": _catalog_movie("551", deleted=True)}

    response = await MovieService(repository, provider).search_movie("film")

    assert response.results == []
    assert response.next_cursor is not None


@pytest.mark.parametrize(("page", "total_pages"), [(3, 3), (500, 900)])
async def test_search_has_no_next_cursor_on_the_last_reachable_page(page, total_pages):
    provider = AsyncMock()
    provider.search_movie.return_value = await _search_page(["550"], page=page, total_pages=total_pages)
    repository = AsyncMock()
    repository.find_movies_by_external_ids.return_value = {}
    cursor = encode_movie_search_cursor(page, query="film", locale="en-US")

    response = await MovieService(repository, provider).search_movie("film", cursor=cursor)

    assert response.next_cursor is None


@pytest.mark.parametrize(
    "cursor",
    [
        "garbage",
        encode_movie_search_cursor(2, query="other film", locale="en-US"),
        encode_movie_search_cursor(2, query="film", locale="it-IT"),
        encode_movie_ref(TMDB_550),
    ],
)
async def test_search_rejects_cursor_issued_for_another_request(cursor):
    provider, repository = AsyncMock(), AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await MovieService(repository, provider).search_movie("film", "en-US", cursor)

    assert exc_info.value.error == ErrorCodes.INVALID_PAGINATION_CURSOR
    provider.search_movie.assert_not_awaited()


async def test_unknown_detail_date_preserves_public_empty_string():
    data = movie_metadata()
    data.common.release_date = None
    provider, repository = AsyncMock(), AsyncMock()
    provider.get_movie_details.return_value = data
    repository.find_movie_by_id.return_value = _catalog_movie()
    assert (await MovieService(repository, provider).get_movie_details(uuid4())).release_date == ""


async def test_provider_canonical_id_cannot_be_imported():
    data = movie_metadata()
    data.canonical_movie_id = uuid4()
    repository, provider = AsyncMock(), AsyncMock()
    repository.find_movie_by_provider.return_value = None
    provider.get_movie_details.return_value = data
    await MovieService(repository, provider).resolve_movie(encode_movie_ref(TMDB_550))
    imported = repository.create_movie.await_args.args[0]
    assert "canonical_movie_id" not in imported.model_dump()
    assert "id" not in imported.model_dump()


async def test_deleted_identity_is_rejected_before_contacting_provider():
    repository, provider = AsyncMock(), AsyncMock()
    repository.find_movie_by_provider.return_value = Mock(deleted=True)
    with pytest.raises(AppException) as error:
        await MovieService(repository, provider).resolve_movie(encode_movie_ref(TMDB_550))
    assert error.value.error == ErrorCodes.MOVIE_UNAVAILABLE
    repository.find_movie_by_provider.assert_awaited_once_with(TMDB_550, include_deleted=True)
    provider.get_movie_details.assert_not_awaited()
    repository.create_movie.assert_not_awaited()


def test_movie_ref_round_trip_is_the_resolved_identity():
    assert decode_movie_ref(encode_movie_ref(TMDB_550)) == TMDB_550
