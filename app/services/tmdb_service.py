import requests
from app.schemas.tmdb_schemas import TMDBMovieSearchResult, TMDBMovieDetails


class TMDBService:
    def __init__(self, api_key):
        self.API_KEY = api_key

    def search_movie(self, query: str) -> TMDBMovieSearchResult:
        """Search for a movie by title."""
        url = f"https://api.themoviedb.org/3/search/movie?query={query}"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.API_KEY}",
        }

        response = requests.get(url, headers=headers)

        return TMDBMovieSearchResult(**response.json())

    def get_movie_details(self, tmdb_id: int) -> TMDBMovieDetails:
        """
        Get full movie details from TMDB by movie ID.

        Returns the complete movie data including:
        - title, overview, release_date
        - poster_path, backdrop_path
        - vote_average, runtime
        - and more
        """
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.API_KEY}",
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        return TMDBMovieDetails(**response.json())
