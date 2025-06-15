import tmdbsimple as tmdb
import requests
from app.schemas.tmdb_schemas import TMDBMovieSearchResult


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