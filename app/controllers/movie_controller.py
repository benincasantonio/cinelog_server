from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request, Response

from app.config.rate_limiter import limiter
from app.dependencies.auth_dependency import auth_dependency
from app.schemas.tmdb_schemas import TMDBMovieSearchResult, TMDBMovieDetails
from app.services.tmdb_service import TMDBService

router = APIRouter()

tmdb_service = TMDBService.get_instance()


@router.get("/search")
@limiter.limit("20/minute")
async def search_movies(
    request: Request,
    response: Response,
    query: str,
    _: PydanticObjectId = Depends(auth_dependency),
) -> TMDBMovieSearchResult:
    """
    Search for movies using TMDB API.
    """
    return await tmdb_service.search_movie(query=query)


@router.get("/{tmdb_id}")
async def get_movie_details(
    tmdb_id: int, _: PydanticObjectId = Depends(auth_dependency)
) -> TMDBMovieDetails:
    """
    Get full movie details from TMDB by movie ID.
    """
    return await tmdb_service.get_movie_details(tmdb_id=tmdb_id)
