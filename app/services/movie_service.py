from uuid import UUID

from app.models.movie_model import Movie
from app.providers.movie_provider_protocol import MovieProviderProtocol
from app.repository.movie_repository_protocol import MovieIdentityUnavailableError, MovieRepositoryProtocol
from app.schemas.movie_api_schemas import (
    MovieDetails,
    MovieGenre,
    MovieProductionCompany,
    MovieProductionCountry,
    MovieSearchResult,
    MovieSearchResultItem,
    MovieSpokenLanguage,
)
from app.schemas.movie_import_schemas import MovieCreateDTO
from app.schemas.movie_provider_schemas import MovieDetailsQuery, MovieSearchQuery, MovieSourceReferenceDTO
from app.types import DEFAULT_LOCALE, MovieProviderName
from app.utils.cursor_pagination_utils import decode_movie_search_cursor, encode_movie_search_cursor
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException
from app.utils.movie_ref_utils import decode_movie_ref, encode_movie_ref

# TMDB serves at most 500 pages for a search query.
MAX_SEARCH_PAGE = 500


class MovieService:
    def __init__(
        self,
        movie_repository: MovieRepositoryProtocol[UUID, Movie],
        provider: MovieProviderProtocol,
    ):
        self.movie_repository = movie_repository
        self.provider = provider

    async def search_movie(
        self, query: str, locale: str = DEFAULT_LOCALE, cursor: str | None = None
    ) -> MovieSearchResult:
        """Return one provider page, naming catalog films by UUID and the rest by movieRef.

        Soft-deleted catalog films are omitted without backfilling, so a page may hold fewer items.
        """
        try:
            page = decode_movie_search_cursor(cursor, query=query, locale=locale) if cursor is not None else 1
        except ValueError as error:
            raise AppException(ErrorCodes.INVALID_PAGINATION_CURSOR) from error

        result = await self.provider.search_movie(MovieSearchQuery(query=query, locale=locale, page=page))

        external_ids_by_source: dict[str, list[str]] = {}
        for item in result.results:
            external_ids_by_source.setdefault(item.source.source, []).append(item.source.external_id)
        catalog = {
            (source, external_id): movie
            for source, external_ids in external_ids_by_source.items()
            for external_id, movie in (
                await self.movie_repository.find_movies_by_external_ids(source, external_ids)
            ).items()
        }

        results = []
        for item in result.results:
            movie = catalog.get((item.source.source, item.source.external_id))
            if movie is not None and movie.deleted:
                continue
            results.append(
                MovieSearchResultItem(
                    id=movie.id if movie is not None else None,
                    movie_ref=encode_movie_ref(item.source) if movie is None else None,
                    title=item.localized.title,
                    overview=item.localized.overview,
                    release_date=item.common.release_date.isoformat() if item.common.release_date else "",
                    poster_path=item.common.poster_path,
                    backdrop_path=item.common.backdrop_path,
                    vote_average=item.external_rating.value,
                    original_title=item.common.original_title,
                    original_language=item.common.original_language,
                    genre_ids=item.common.genre_ids,
                )
            )

        has_next_page = result.page < min(result.total_pages, MAX_SEARCH_PAGE)
        return MovieSearchResult(
            results=results,
            next_cursor=(
                encode_movie_search_cursor(result.page + 1, query=query, locale=locale) if has_next_page else None
            ),
        )

    async def resolve_movie(self, movie_ref: str) -> UUID:
        """Return the catalog UUID of a search result, importing it on first selection only."""
        try:
            source = decode_movie_ref(movie_ref)
        except ValueError as error:
            raise AppException(ErrorCodes.INVALID_MOVIE_REF) from error

        movie = await self._find_or_import_movie(source)
        return movie.id

    async def get_movie_details(self, movie_id: UUID, locale: str = DEFAULT_LOCALE) -> MovieDetails:
        """Read live provider details for an active catalog movie through its mapping."""
        movie = await self.get_active_movie(movie_id)
        mapping = next((item for item in movie.providers if item.provider == MovieProviderName.TMDB), None)
        if mapping is None:
            raise AppException(ErrorCodes.MOVIE_NOT_FOUND)

        metadata = await self.provider.get_movie_details(
            MovieDetailsQuery(external_id=mapping.external_id, locale=locale)
        )
        common, localized = metadata.common, metadata.localized
        return MovieDetails(
            id=movie.id,
            title=localized.title,
            original_title=common.original_title,
            overview=localized.overview,
            release_date=common.release_date.isoformat() if common.release_date else "",
            poster_path=common.poster_path,
            backdrop_path=common.backdrop_path,
            vote_average=metadata.external_rating.value,
            vote_count=metadata.external_rating.vote_count,
            runtime=common.runtime,
            budget=common.budget,
            revenue=common.revenue,
            status=common.status,
            tagline=localized.tagline,
            homepage=common.homepage,
            imdb_id=common.imdb_id,
            original_language=common.original_language,
            popularity=common.popularity,
            adult=common.adult,
            genres=[MovieGenre.model_validate(genre) for genre in localized.genres],
            production_companies=[MovieProductionCompany.model_validate(item) for item in common.production_companies],
            production_countries=[MovieProductionCountry.model_validate(item) for item in common.production_countries],
            spoken_languages=[MovieSpokenLanguage.model_validate(item) for item in common.spoken_languages],
        )

    async def get_movie_by_id(self, movie_id: UUID):
        """Find a movie by its ID."""
        return await self.movie_repository.find_movie_by_id(movie_id)

    async def get_active_movie(self, movie_id: UUID) -> Movie:
        """Find an active movie by UUID; unknown and soft-deleted movies are both not found."""
        movie = await self.movie_repository.find_movie_by_id(movie_id)
        if movie is None:
            raise AppException(ErrorCodes.MOVIE_NOT_FOUND)
        return movie

    async def _find_or_import_movie(self, source: MovieSourceReferenceDTO) -> Movie:
        """Find a source identity, or import it; a soft-deleted identity stays reserved."""

        movie = await self.movie_repository.find_movie_by_provider(source, include_deleted=True)

        if movie:
            if movie.deleted:
                raise AppException(ErrorCodes.MOVIE_UNAVAILABLE)
            return movie

        metadata = await self.provider.get_movie_details(
            MovieDetailsQuery(external_id=source.external_id, locale=DEFAULT_LOCALE)
        )
        try:
            return await self.movie_repository.create_movie(MovieCreateDTO.from_metadata(metadata))
        except MovieIdentityUnavailableError as error:
            raise AppException(ErrorCodes.MOVIE_UNAVAILABLE) from error
