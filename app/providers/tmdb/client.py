"""Bounded TMDB HTTP access and safe application errors."""

import os

import httpx
from pydantic import BaseModel, ValidationError

from app.providers.tmdb.schemas import TMDBMovieDetails, TMDBMovieSearchResult
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException

TMDB_TIMEOUT = int(os.getenv("TMDB_TIMEOUT", "10"))
TMDB_BASE_URL = "https://api.themoviedb.org/3"


class TMDBClient:
    def __init__(self, api_key: str | None = None, client: httpx.AsyncClient | None = None):
        if TMDB_TIMEOUT <= 0:
            raise ValueError("TMDB_TIMEOUT must be positive")
        self._api_key = api_key if api_key is not None else os.getenv("TMDB_API_KEY")
        self._client = client if client is not None else httpx.AsyncClient(timeout=TMDB_TIMEOUT)
        self._owns_client = client is None
        self._closed = False

    async def _request[Result: BaseModel](
        self, path: str, params: dict[str, str], schema: type[Result], *, movie_detail: bool = False
    ) -> Result:
        if self._closed:
            raise RuntimeError("TMDBClient is closed")
        try:
            response = await self._client.get(
                f"{TMDB_BASE_URL}{path}",
                headers={"accept": "application/json", "Authorization": f"Bearer {self._api_key}"},
                params=params,
                timeout=httpx.Timeout(TMDB_TIMEOUT),
            )
        except httpx.RequestError:
            raise AppException(ErrorCodes.MOVIE_PROVIDER_UNAVAILABLE) from None

        if movie_detail and response.status_code == 404:
            raise AppException(ErrorCodes.PROVIDER_MOVIE_NOT_FOUND)
        if response.status_code == 429 or response.status_code >= 500:
            raise AppException(ErrorCodes.MOVIE_PROVIDER_UNAVAILABLE)
        if not response.is_success:
            raise AppException(ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE)
        try:
            return schema.model_validate(response.json())
        except (ValidationError, ValueError):
            raise AppException(ErrorCodes.MOVIE_PROVIDER_INVALID_RESPONSE) from None

    async def search_movie(self, query: str, locale: str) -> TMDBMovieSearchResult:
        return await self._request("/search/movie", {"query": query, "language": locale}, TMDBMovieSearchResult)

    async def get_movie_details(self, external_id: str, locale: str) -> TMDBMovieDetails:
        # Keep the legacy integer API, and never interpolate arbitrary paths.
        try:
            movie_id = int(external_id)
        except ValueError:
            raise AppException(ErrorCodes.PROVIDER_MOVIE_NOT_FOUND) from None
        if movie_id <= 0:
            raise AppException(ErrorCodes.PROVIDER_MOVIE_NOT_FOUND)
        return await self._request(f"/movie/{movie_id}", {"language": locale}, TMDBMovieDetails, movie_detail=True)

    async def aclose(self) -> None:
        if self._closed or not self._owns_client:
            return
        await self._client.aclose()
        self._closed = True
