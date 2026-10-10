"""TMDB adapter: validated source observations mapped to Cinelog metadata."""

from datetime import UTC, datetime
from threading import Lock

from app.providers.tmdb.cache import TMDBCache
from app.providers.tmdb.client import TMDBClient
from app.providers.tmdb.schemas import (
    TMDBDetailsSnapshot,
    TMDBMovieDetails,
    TMDBMovieSearchResult,
    TMDBSearchSnapshot,
)
from app.schemas.movie_provider_schemas import (
    ExternalMovieDetailsRatingDTO,
    ExternalMovieRatingDTO,
    MovieCommonDetailsDTO,
    MovieCommonMetadataDTO,
    MovieCompanyMetadataDTO,
    MovieCountryMetadataDTO,
    MovieDetailsQuery,
    MovieGenreMetadataDTO,
    MovieLanguageMetadataDTO,
    MovieLocalizedDetailsDTO,
    MovieLocalizedTextDTO,
    MovieMetadataDTO,
    MovieSearchItemDTO,
    MovieSearchQuery,
    MovieSearchResultDTO,
    MovieSourceReferenceDTO,
)
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class TMDBMovieProvider:
    _singleton: "TMDBMovieProvider | None" = None
    _singleton_lock = Lock()

    def __init__(self, client: TMDBClient | None = None, cache: TMDBCache | None = None):
        self._client = client if client is not None else TMDBClient()
        self._owns_client = client is None
        self._cache = cache if cache is not None else TMDBCache()
        self._closed = False

    @classmethod
    def get_instance(cls) -> "TMDBMovieProvider":
        with cls._singleton_lock:
            if cls._singleton is None:
                cls._singleton = cls()
            return cls._singleton

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("TMDBMovieProvider is closed")

    async def search_movie(self, request: MovieSearchQuery) -> MovieSearchResultDTO:
        self._ensure_open()
        try:
            cached = await self._cache.get_search(request.query, request.locale)
            if cached is not None:
                return self._map_search(cached.payload, request.locale, cached.observed_at)
            payload = await self._client.search_movie(request.query, request.locale)
            result = self._map_search(payload, request.locale)
            await self._cache.set_search(
                request.query, request.locale, TMDBSearchSnapshot(payload=payload, observed_at=result.observed_at)
            )
            return result
        except ValueError:
            raise AppException(ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE) from None

    async def get_movie_details(self, request: MovieDetailsQuery) -> MovieMetadataDTO:
        self._ensure_open()
        try:
            if request.force_refresh:
                generation = await self._cache.invalidate_details(request.external_id, request.locale)
                cached = None
            else:
                cached, generation = await self._cache.get_details(request.external_id, request.locale)
            payload = (
                cached.payload
                if cached is not None
                else await self._client.get_movie_details(request.external_id, request.locale)
            )
            if str(payload.id) != request.external_id:
                raise ValueError("Provider returned a different movie identity")
            result = self._map_details(payload, request.locale, cached.observed_at if cached is not None else None)
            if cached is None:
                await self._cache.set_details(
                    request.external_id,
                    request.locale,
                    TMDBDetailsSnapshot(payload=payload, observed_at=result.observed_at),
                    generation,
                )
            return result
        except ValueError:
            raise AppException(ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE) from None

    @staticmethod
    def _map_search(
        data: TMDBMovieSearchResult, locale: str, observed_at: datetime | None = None
    ) -> MovieSearchResultDTO:
        return MovieSearchResultDTO(
            page=data.page,
            total_results=data.total_results,
            total_pages=data.total_pages,
            results=[
                MovieSearchItemDTO(
                    source=MovieSourceReferenceDTO(source="tmdb", external_id=str(item.id)),
                    common=MovieCommonMetadataDTO(
                        original_title=item.original_title,
                        original_language=item.original_language,
                        release_date=item.release_date,
                        poster_path=item.poster_path,
                        backdrop_path=item.backdrop_path,
                        genre_ids=item.genre_ids,
                    ),
                    localized=MovieLocalizedTextDTO(locale=locale, title=item.title, overview=item.overview),
                    external_rating=ExternalMovieRatingDTO(source="tmdb", value=item.vote_average, scale=10),
                )
                for item in data.results
                if item.title is not None and item.title.strip()
            ],
            # Read the clock only after constructing and validating the mapped fields.
            observed_at=observed_at if observed_at is not None else datetime.now(UTC),
        )

    @staticmethod
    def _map_details(data: TMDBMovieDetails, locale: str, observed_at: datetime | None = None) -> MovieMetadataDTO:
        return MovieMetadataDTO(
            source=MovieSourceReferenceDTO(source="tmdb", external_id=str(data.id)),
            source_payload=data.model_dump(mode="json"),
            external_rating=ExternalMovieDetailsRatingDTO(
                source="tmdb", value=data.vote_average, scale=10, vote_count=data.vote_count
            ),
            localized=MovieLocalizedDetailsDTO(
                locale=locale,
                title=data.title,
                overview=data.overview,
                tagline=data.tagline,
                genres=[MovieGenreMetadataDTO(id=genre.id, name=genre.name) for genre in data.genres],
            ),
            common=MovieCommonDetailsDTO(
                original_title=data.original_title,
                original_language=data.original_language,
                release_date=data.release_date,
                poster_path=data.poster_path,
                backdrop_path=data.backdrop_path,
                genre_ids=[genre.id for genre in data.genres],
                runtime=data.runtime,
                budget=data.budget,
                revenue=data.revenue,
                status=data.status,
                homepage=data.homepage,
                imdb_id=data.imdb_id,
                popularity=data.popularity,
                adult=data.adult,
                production_companies=[
                    MovieCompanyMetadataDTO(
                        id=company.id,
                        name=company.name,
                        logo_path=company.logo_path,
                        origin_country=company.origin_country,
                    )
                    for company in data.production_companies
                ],
                production_countries=[
                    MovieCountryMetadataDTO(iso_3166_1=country.iso_3166_1, name=country.name)
                    for country in data.production_countries
                ],
                spoken_languages=[
                    MovieLanguageMetadataDTO(
                        iso_639_1=language.iso_639_1, name=language.name, english_name=language.english_name
                    )
                    for language in data.spoken_languages
                ],
            ),
            # Cached observations retain their timestamp; fresh ones are stamped once.
            observed_at=observed_at if observed_at is not None else datetime.now(UTC),
        )

    async def aclose(self) -> None:
        if self._closed:
            return
        if self._owns_client:
            await self._client.aclose()
        self._closed = True
        with self._singleton_lock:
            if type(self)._singleton is self:
                type(self)._singleton = None

    @classmethod
    async def aclose_all(cls) -> None:
        with cls._singleton_lock:
            singleton = cls._singleton
            cls._singleton = None
        if singleton is not None:
            await singleton.aclose()
