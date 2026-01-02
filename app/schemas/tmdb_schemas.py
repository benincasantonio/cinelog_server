from pydantic import BaseModel, Field, ConfigDict


class TMDBMovieSearchResult(BaseModel):
    """Results for movie search from TMDB"""

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(..., description="Current page of results")
    totalResults: int = Field(
        ...,
        validation_alias="total_results",
        description="Total number of results found",
    )
    totalPages: int = Field(
        ...,
        validation_alias="total_pages",
        description="Total number of pages available",
    )
    results: list["TMDBMovieSearchResultItem"] = Field(
        ..., description="List of movie search result items"
    )


class TMDBMovieSearchResultItem(BaseModel):
    """Single movie item in TMDB search results"""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Unique identifier for the movie")
    title: str = Field(..., description="Title of the movie")
    overview: str = Field(..., description="Overview of the movie")
    releaseDate: str = Field(
        ...,
        validation_alias="release_date",
        description="Release date of the movie in YYYY-MM-DD format",
    )
    posterPath: str | None = Field(
        None,
        validation_alias="poster_path",
        description="Path to the movie poster image",
    )
    voteAverage: float = Field(
        ..., validation_alias="vote_average", description="Average rating of the movie"
    )
    backdropPath: str | None = Field(
        None,
        validation_alias="backdrop_path",
        description="Path to the movie backdrop image",
    )
    genreIds: list[int] = Field(
        ...,
        validation_alias="genre_ids",
        description="List of genre IDs associated with the movie",
    )
    originalLanguage: str = Field(
        ...,
        validation_alias="original_language",
        description="Original language of the movie",
    )
    originalTitle: str = Field(
        ...,
        validation_alias="original_title",
        description="Original title of the movie",
    )


class TMDBGenre(BaseModel):
    """Genre information from TMDB"""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Unique identifier for the genre")
    name: str = Field(..., description="Name of the genre")


class TMDBProductionCompany(BaseModel):
    """Production company information from TMDB"""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Unique identifier for the production company")
    name: str = Field(..., description="Name of the production company")
    logoPath: str | None = Field(
        None, validation_alias="logo_path", description="Path to the company logo"
    )
    originCountry: str = Field(
        ...,
        validation_alias="origin_country",
        description="Country of origin for the company",
    )


class TMDBProductionCountry(BaseModel):
    """Production country information from TMDB"""

    model_config = ConfigDict(populate_by_name=True)

    iso31661: str = Field(
        ..., validation_alias="iso_3166_1", description="ISO 3166-1 country code"
    )
    name: str = Field(..., description="Country name")


class TMDBSpokenLanguage(BaseModel):
    """Spoken language information from TMDB"""

    model_config = ConfigDict(populate_by_name=True)

    iso6391: str = Field(
        ..., validation_alias="iso_639_1", description="ISO 639-1 language code"
    )
    name: str = Field(..., description="Language name")
    englishName: str = Field(
        ..., validation_alias="english_name", description="English name of the language"
    )


class TMDBMovieDetails(BaseModel):
    """Full movie details from TMDB"""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Unique identifier for the movie")
    title: str = Field(..., description="Title of the movie")
    originalTitle: str = Field(
        ...,
        validation_alias="original_title",
        description="Original title of the movie",
    )
    overview: str = Field(..., description="Overview of the movie")
    releaseDate: str = Field(
        ...,
        validation_alias="release_date",
        description="Release date of the movie in YYYY-MM-DD format",
    )
    posterPath: str | None = Field(
        None,
        validation_alias="poster_path",
        description="Path to the movie poster image",
    )
    backdropPath: str | None = Field(
        None,
        validation_alias="backdrop_path",
        description="Path to the movie backdrop image",
    )
    voteAverage: float = Field(
        ..., validation_alias="vote_average", description="Average rating of the movie"
    )
    voteCount: int = Field(
        ..., validation_alias="vote_count", description="Number of votes"
    )
    runtime: int | None = Field(None, description="Runtime in minutes")
    budget: int = Field(..., description="Budget of the movie")
    revenue: int = Field(..., description="Revenue of the movie")
    status: str = Field(..., description="Release status of the movie")
    tagline: str | None = Field(None, description="Tagline of the movie")
    homepage: str | None = Field(None, description="Official homepage URL")
    imdbId: str | None = Field(None, validation_alias="imdb_id", description="IMDB ID")
    originalLanguage: str = Field(
        ...,
        validation_alias="original_language",
        description="Original language of the movie",
    )
    popularity: float = Field(..., description="Popularity score")
    adult: bool = Field(..., description="Whether the movie is adult content")
    genres: list[TMDBGenre] = Field(..., description="List of genres")
    productionCompanies: list[TMDBProductionCompany] = Field(
        ...,
        validation_alias="production_companies",
        description="List of production companies",
    )
    productionCountries: list[TMDBProductionCountry] = Field(
        ...,
        validation_alias="production_countries",
        description="List of production countries",
    )
    spokenLanguages: list[TMDBSpokenLanguage] = Field(
        ..., validation_alias="spoken_languages", description="List of spoken languages"
    )
