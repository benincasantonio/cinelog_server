"""Public movie API contract, owned by Cinelog: canonical UUIDs and backend-issued movie references."""

from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.schemas.base_schemas import BaseSchema


class MovieSearchResultItem(BaseSchema):
    """Single movie item in movie search results.

    Exactly one identity is set: ``id`` for a film already in the Cinelog catalog,
    otherwise ``movieRef``, which must be resolved before navigation or writes.
    """

    id: UUID | None = Field(None, description="Cinelog movie UUID, when the film is already in the catalog")
    movie_ref: str | None = Field(
        None, description="Opaque backend-issued reference to resolve via POST /v1/movies/resolve"
    )
    title: str = Field(..., description="Title of the movie")
    overview: str = Field(..., description="Overview of the movie")
    release_date: str = Field(
        ...,
        validation_alias="release_date",
        description="Release date of the movie in YYYY-MM-DD format",
    )
    poster_path: str | None = Field(
        None,
        validation_alias="poster_path",
        description="Path to the movie poster image",
    )
    vote_average: float = Field(..., validation_alias="vote_average", description="Average rating of the movie")
    backdrop_path: str | None = Field(
        None,
        validation_alias="backdrop_path",
        description="Path to the movie backdrop image",
    )
    genre_ids: list[int] = Field(
        ...,
        validation_alias="genre_ids",
        description="List of genre IDs associated with the movie",
    )
    original_language: str = Field(
        ...,
        validation_alias="original_language",
        description="Original language of the movie",
    )
    original_title: str = Field(
        ...,
        validation_alias="original_title",
        description="Original title of the movie",
    )

    @model_validator(mode="after")
    def validate_single_identity(self) -> Self:
        if (self.id is None) == (self.movie_ref is None):
            raise ValueError("Exactly one of id and movieRef must be set")
        return self


class MovieSearchResult(BaseSchema):
    """One provider page of movie search results, without soft-deleted catalog films"""

    results: list[MovieSearchResultItem] = Field(..., description="List of movie search result items")
    next_cursor: str | None = Field(None, description="Opaque cursor for the next page, or null on the last page")


class MovieResolveRequest(BaseSchema):
    """Request to materialize a search result as a Cinelog movie"""

    model_config = ConfigDict(extra="forbid")

    movie_ref: str = Field(..., min_length=1, description="movieRef returned by GET /v1/movies/search")


class MovieResolveResponse(BaseSchema):
    """Canonical identity of a resolved search result"""

    movie_id: UUID = Field(..., description="Cinelog movie UUID")


class MovieGenre(BaseSchema):
    """Genre information from the external movie catalog"""

    id: int = Field(..., description="Unique identifier for the genre")
    name: str = Field(..., description="Name of the genre")


class MovieProductionCompany(BaseSchema):
    """Production company information from the external movie catalog"""

    id: int = Field(..., description="Unique identifier for the production company")
    name: str = Field(..., description="Name of the production company")
    logo_path: str | None = Field(None, validation_alias="logo_path", description="Path to the company logo")
    origin_country: str = Field(
        ...,
        validation_alias="origin_country",
        description="Country of origin for the company",
    )


class MovieProductionCountry(BaseSchema):
    """Production country information from the external movie catalog"""

    iso_3166_1: str = Field(..., validation_alias="iso_3166_1", description="ISO 3166-1 country code")
    name: str = Field(..., description="Country name")


class MovieSpokenLanguage(BaseSchema):
    """Spoken language information from the external movie catalog"""

    iso_639_1: str = Field(..., validation_alias="iso_639_1", description="ISO 639-1 language code")
    name: str = Field(..., description="Language name")
    english_name: str = Field(..., validation_alias="english_name", description="English name of the language")


class MovieDetails(BaseSchema):
    """Full movie details for a Cinelog movie, read live from its provider"""

    id: UUID = Field(..., description="Cinelog movie UUID")
    title: str = Field(..., description="Title of the movie")
    original_title: str = Field(
        ...,
        validation_alias="original_title",
        description="Original title of the movie",
    )
    overview: str = Field(..., description="Overview of the movie")
    release_date: str = Field(
        ...,
        validation_alias="release_date",
        description="Release date of the movie in YYYY-MM-DD format",
    )
    poster_path: str | None = Field(
        None,
        validation_alias="poster_path",
        description="Path to the movie poster image",
    )
    backdrop_path: str | None = Field(
        None,
        validation_alias="backdrop_path",
        description="Path to the movie backdrop image",
    )
    vote_average: float = Field(..., validation_alias="vote_average", description="Average rating of the movie")
    vote_count: int = Field(..., validation_alias="vote_count", description="Number of votes")
    runtime: int | None = Field(None, description="Runtime in minutes")
    budget: int = Field(..., description="Budget of the movie")
    revenue: int = Field(..., description="Revenue of the movie")
    status: str = Field(..., description="Release status of the movie")
    tagline: str | None = Field(None, description="Tagline of the movie")
    homepage: str | None = Field(None, description="Official homepage URL")
    imdb_id: str | None = Field(None, validation_alias="imdb_id", description="IMDB ID")
    original_language: str = Field(
        ...,
        validation_alias="original_language",
        description="Original language of the movie",
    )
    popularity: float = Field(..., description="Popularity score")
    adult: bool = Field(..., description="Whether the movie is adult content")
    genres: list[MovieGenre] = Field(..., description="List of genres")
    production_companies: list[MovieProductionCompany] = Field(
        ...,
        validation_alias="production_companies",
        description="List of production companies",
    )
    production_countries: list[MovieProductionCountry] = Field(
        ...,
        validation_alias="production_countries",
        description="List of production countries",
    )
    spoken_languages: list[MovieSpokenLanguage] = Field(
        ..., validation_alias="spoken_languages", description="List of spoken languages"
    )
