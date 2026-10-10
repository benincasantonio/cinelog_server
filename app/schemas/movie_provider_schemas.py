"""Cinelog-owned provider queries and result DTOs.

Search observations do not establish complete detail synchronization. A source
payload is an opaque diagnostic snapshot, never a canonical movie identifier.
"""

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from app.types import DEFAULT_LOCALE, LocaleStr


class MovieSearchQuery(BaseModel):
    query: str
    locale: LocaleStr = DEFAULT_LOCALE


class MovieDetailsQuery(BaseModel):
    external_id: str = Field(min_length=1)
    locale: LocaleStr = DEFAULT_LOCALE
    force_refresh: bool = False


class MovieSourceReferenceDTO(BaseModel):
    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)


class ExternalMovieRatingDTO(BaseModel):
    source: str
    value: float
    scale: float = Field(gt=0)
    vote_count: int | None = None


class ExternalMovieDetailsRatingDTO(ExternalMovieRatingDTO):
    vote_count: int


class MovieGenreMetadataDTO(BaseModel):
    id: int
    name: str


class MovieCompanyMetadataDTO(BaseModel):
    id: int
    name: str
    logo_path: str | None = None
    origin_country: str


class MovieCountryMetadataDTO(BaseModel):
    iso_3166_1: str
    name: str


class MovieLanguageMetadataDTO(BaseModel):
    iso_639_1: str
    name: str
    english_name: str


class MovieCommonMetadataDTO(BaseModel):
    original_title: str
    original_language: str
    release_date: date | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    genre_ids: list[int]


class MovieCommonDetailsDTO(MovieCommonMetadataDTO):
    runtime: int | None = None
    budget: int
    revenue: int
    status: str
    homepage: str | None = None
    imdb_id: str | None = None
    popularity: float
    adult: bool
    production_companies: list[MovieCompanyMetadataDTO]
    production_countries: list[MovieCountryMetadataDTO]
    spoken_languages: list[MovieLanguageMetadataDTO]


class MovieLocalizedTextDTO(BaseModel):
    # This is the requested provider locale, not proof of an upstream translation.
    locale: LocaleStr
    title: str
    overview: str


class MovieLocalizedDetailsDTO(MovieLocalizedTextDTO):
    tagline: str | None = None
    genres: list[MovieGenreMetadataDTO]


class MovieSearchItemDTO(BaseModel):
    source: MovieSourceReferenceDTO
    canonical_movie_id: UUID | None = None
    common: MovieCommonMetadataDTO
    localized: MovieLocalizedTextDTO
    external_rating: ExternalMovieRatingDTO


class MovieSearchResultDTO(BaseModel):
    page: int
    total_results: int
    total_pages: int
    results: list[MovieSearchItemDTO]
    observed_at: AwareDatetime


class MovieMetadataDTO(BaseModel):
    source: MovieSourceReferenceDTO
    canonical_movie_id: UUID | None = None
    common: MovieCommonDetailsDTO
    localized: MovieLocalizedDetailsDTO
    external_rating: ExternalMovieDetailsRatingDTO
    observed_at: AwareDatetime
    source_payload: dict[str, Any] = Field(repr=False)
