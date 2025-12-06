from fastapi import APIRouter, Depends

from app.dependencies import auth_dependency
from app.schemas.tmdb_schemas import TMDBMovieSearchResult
from app.services.tmdb_service import TMDBService
from app.utils.exceptions import AppException
from os import getenv

router = APIRouter()

TMDB_API_KEY = getenv("TMDB_API_KEY")
tmdb_service = TMDBService(api_key=TMDB_API_KEY)


@router.get("/search")
def search_movies(
    query: str, _: bool = Depends(auth_dependency)
) -> TMDBMovieSearchResult:
    """
    Search for movies using TMDB API.
    """
    try:
        return tmdb_service.search_movie(query=query)
    except AppException as e:
        raise e
