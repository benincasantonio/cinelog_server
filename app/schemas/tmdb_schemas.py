from pydantic import Field

from app.schemas.base_schema import BaseSchema


class TMDBMovieSearchResultItem(BaseSchema):
    """Single movie item in TMDB search results"""

    id: int = Field(..., description="Unique identifier for the movie")
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
    vote_average: float = Field(
        ..., validation_alias="vote_average", description="Average rating of the movie"
    )
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


class TMDBMovieSearchResult(BaseSchema):
    """Results for movie search from TMDB"""

    page: int = Field(..., description="Current page of results")
    total_results: int = Field(
        ...,
        validation_alias="total_results",
        description="Total number of results found",
    )
    total_pages: int = Field(
        ...,
        validation_alias="total_pages",
        description="Total number of pages available",
    )
    results: list[TMDBMovieSearchResultItem] = Field(
        ..., description="List of movie search result items"
    )


class TMDBGenre(BaseSchema):
    """Genre information from TMDB"""

    id: int = Field(..., description="Unique identifier for the genre")
    name: str = Field(..., description="Name of the genre")


class TMDBProductionCompany(BaseSchema):
    """Production company information from TMDB"""

    id: int = Field(..., description="Unique identifier for the production company")
    name: str = Field(..., description="Name of the production company")
    logo_path: str | None = Field(
        None, validation_alias="logo_path", description="Path to the company logo"
    )
    origin_country: str = Field(
        ...,
        validation_alias="origin_country",
        description="Country of origin for the company",
    )


class TMDBProductionCountry(BaseSchema):
    """Production country information from TMDB"""

    iso_3166_1: str = Field(
        ..., validation_alias="iso_3166_1", description="ISO 3166-1 country code"
    )
    name: str = Field(..., description="Country name")


class TMDBSpokenLanguage(BaseSchema):
    """Spoken language information from TMDB"""

    iso_639_1: str = Field(
        ..., validation_alias="iso_639_1", description="ISO 639-1 language code"
    )
    name: str = Field(..., description="Language name")
    english_name: str = Field(
        ..., validation_alias="english_name", description="English name of the language"
    )


class TMDBMovieDetails(BaseSchema):
    """Full movie details from TMDB"""

    id: int = Field(..., description="Unique identifier for the movie")
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
    vote_average: float = Field(
        ..., validation_alias="vote_average", description="Average rating of the movie"
    )
    vote_count: int = Field(
        ..., validation_alias="vote_count", description="Number of votes"
    )
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
    genres: list[TMDBGenre] = Field(..., description="List of genres")
    production_companies: list[TMDBProductionCompany] = Field(
        ...,
        validation_alias="production_companies",
        description="List of production companies",
    )
    production_countries: list[TMDBProductionCountry] = Field(
        ...,
        validation_alias="production_countries",
        description="List of production countries",
    )
    spoken_languages: list[TMDBSpokenLanguage] = Field(
        ..., validation_alias="spoken_languages", description="List of spoken languages"
    )
