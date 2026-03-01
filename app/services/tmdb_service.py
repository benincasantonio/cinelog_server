import httpx
import os
from threading import Lock

from app.schemas.tmdb_schemas import TMDBMovieSearchResult, TMDBMovieDetails


class TMDBService:
    _singleton: "TMDBService | None" = None
    _singleton_lock = Lock()

    def __init__(
        self, api_key: str | None = None, client: httpx.AsyncClient | None = None
    ):
        self.API_KEY = api_key if api_key is not None else os.getenv("TMDB_API_KEY")
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._closed = False

    @classmethod
    def get_instance(cls) -> "TMDBService":
        with cls._singleton_lock:
            if cls._singleton is None:
                cls._singleton = cls()
            return cls._singleton

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self.API_KEY}",
        }

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("TMDBService client is closed")

    async def search_movie(self, query: str) -> TMDBMovieSearchResult:
        """Search for a movie by title."""
        self._ensure_open()
        url = "https://api.themoviedb.org/3/search/movie"

        response = await self._client.get(
            url, headers=self._headers(), params={"query": query}
        )

        return TMDBMovieSearchResult(**response.json())

    async def get_movie_details(self, tmdb_id: int) -> TMDBMovieDetails:
        """
        Get full movie details from TMDB by movie ID.

        Returns the complete movie data including:
        - title, overview, release_date
        - poster_path, backdrop_path
        - vote_average, runtime
        - and more
        """
        self._ensure_open()
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"

        response = await self._client.get(url, headers=self._headers())
        response.raise_for_status()  # Raise exception for bad status codes

        return TMDBMovieDetails(**response.json())

    async def aclose(self) -> None:
        if not self._owns_client or self._closed:
            return
        await self._client.aclose()
        self._closed = True
        with TMDBService._singleton_lock:
            if TMDBService._singleton is self:
                TMDBService._singleton = None

    @classmethod
    async def aclose_all(cls) -> None:
        with cls._singleton_lock:
            singleton = cls._singleton
            cls._singleton = None
        if singleton is not None:
            await singleton.aclose()
