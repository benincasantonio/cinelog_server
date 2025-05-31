from pydantic import BaseModel, Field


class TMDBMovieSearchResult(BaseModel):
    """Results for movie search from TMDB"""
    page: int = Field(..., description="Current page of results")
    total_results: int = Field(..., description="Total number of results found")
    total_pages: int = Field(..., description="Total number of pages available")
    results: list['TMDBMovieSearchResultItem'] = Field(..., description="List of movie search result items")


class TMDBMovieSearchResultItem(BaseModel):
    """Single movie item in TMDB search results"""
    id: int = Field(..., description="Unique identifier for the movie")
    title: str = Field(..., description="Title of the movie")
    overview: str = Field(..., description="Overview of the movie")
    release_date: str = Field(..., description="Release date of the movie in YYYY-MM-DD format")
    poster_path: str | None = Field(None, description="Path to the movie poster image")
    vote_average: float = Field(..., description="Average rating of the movie")
    backdrop_path: str | None = Field(None, description="Path to the movie backdrop image")
    genre_ids: list[int] = Field(..., description="List of genre IDs associated with the movie")
    original_language: str = Field(..., description="Original language of the movie")
    original_title: str = Field(..., description="Original title of the movie")