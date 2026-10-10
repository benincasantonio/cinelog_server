"""Private TMDB wire DTOs and cache envelopes; never used by generic consumers."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.providers.tmdb.validation import TMDBReleaseDate, TMDBVoteAverage


class TMDBSchema(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)


class TMDBMovieSearchResultItem(TMDBSchema):
    id: int = Field(gt=0)
    # The provider omits untitled items after validating the remaining fields.
    title: str | None = None
    overview: str
    release_date: TMDBReleaseDate = None
    poster_path: str | None = None
    vote_average: TMDBVoteAverage
    backdrop_path: str | None = None
    genre_ids: list[int]
    original_language: str
    original_title: str


class TMDBMovieSearchResult(TMDBSchema):
    page: int = Field(ge=1)
    total_results: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    results: list[TMDBMovieSearchResultItem]


class TMDBGenre(TMDBSchema):
    id: int
    name: str


class TMDBProductionCompany(TMDBSchema):
    id: int
    name: str
    logo_path: str | None = None
    origin_country: str


class TMDBProductionCountry(TMDBSchema):
    iso_3166_1: str
    name: str


class TMDBSpokenLanguage(TMDBSchema):
    iso_639_1: str
    name: str
    english_name: str


class TMDBMovieDetails(TMDBSchema):
    id: int = Field(gt=0)
    title: str = Field(min_length=1, pattern=r"\S")
    original_title: str
    overview: str
    release_date: TMDBReleaseDate = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: TMDBVoteAverage
    vote_count: int = Field(ge=0)
    runtime: int | None = Field(default=None, ge=0)
    budget: int
    revenue: int
    status: str
    tagline: str | None = None
    homepage: str | None = None
    imdb_id: str | None = None
    original_language: str
    popularity: float
    adult: bool
    genres: list[TMDBGenre]
    production_companies: list[TMDBProductionCompany]
    production_countries: list[TMDBProductionCountry]
    spoken_languages: list[TMDBSpokenLanguage]


class TMDBSearchSnapshot(BaseModel):
    payload: TMDBMovieSearchResult
    observed_at: AwareDatetime


class TMDBDetailsSnapshot(BaseModel):
    payload: TMDBMovieDetails
    observed_at: AwareDatetime
