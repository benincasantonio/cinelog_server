from uuid import UUID

from app.providers.movie_provider_protocol import MovieProviderProtocol
from app.repository.movie_repository_protocol import MovieRepositoryProtocol
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
from app.schemas.movie_provider_schemas import MovieDetailsQuery, MovieSearchQuery
from app.types import DEFAULT_LOCALE


class MovieService:
    def __init__(
        self,
        movie_repository: MovieRepositoryProtocol,
        provider: MovieProviderProtocol,
    ):
        self.movie_repository = movie_repository
        self.provider = provider

    async def search_movie(self, query: str, locale: str = DEFAULT_LOCALE) -> MovieSearchResult:
        result = await self.provider.search_movie(MovieSearchQuery(query=query, locale=locale))
        return MovieSearchResult(
            page=result.page,
            total_results=result.total_results,
            total_pages=result.total_pages,
            results=[
                MovieSearchResultItem(
                    id=int(item.source.external_id),
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
                for item in result.results
            ],
        )

    async def get_movie_details(self, tmdb_id: int, locale: str = DEFAULT_LOCALE) -> MovieDetails:
        metadata = await self.provider.get_movie_details(MovieDetailsQuery(external_id=str(tmdb_id), locale=locale))
        common, localized = metadata.common, metadata.localized
        return MovieDetails(
            id=int(metadata.source.external_id),
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

    async def get_movie_by_tmdb_id(self, tmdb_id: int):
        """Find a movie by its TMDB ID."""
        return await self.movie_repository.find_movie_by_tmdb_id(tmdb_id)

    async def find_or_create_movie(self, tmdb_id: int):
        """Find a movie by TMDB ID, or create it if it doesn't exist."""

        movie = await self.movie_repository.find_movie_by_tmdb_id(tmdb_id)

        if movie:
            return movie

        metadata = await self.provider.get_movie_details(
            MovieDetailsQuery(external_id=str(tmdb_id), locale=DEFAULT_LOCALE)
        )
        return await self.movie_repository.create_movie(MovieCreateDTO.from_metadata(metadata))
