from fastapi import APIRouter, Depends, Request, Response

from app.config.rate_limiter import limiter
from app.dependencies.locale_dependency import locale_dependency
from app.dependencies.service_dependency import get_movie_service
from app.schemas.movie_api_schemas import MovieDetails, MovieSearchResult
from app.services.movie_service import MovieService

router = APIRouter()


@router.get("/search")
@limiter.limit("20/minute")
async def search_movies(
    request: Request,
    response: Response,
    query: str,
    locale: str = Depends(locale_dependency),
    movie_service: MovieService = Depends(get_movie_service),
) -> MovieSearchResult:
    """
    Search for movies using TMDB API.
    """
    return await movie_service.search_movie(query=query, locale=locale)


@router.get("/{tmdb_id}")
async def get_movie_details(
    tmdb_id: int,
    locale: str = Depends(locale_dependency),
    movie_service: MovieService = Depends(get_movie_service),
) -> MovieDetails:
    """
    Get full movie details from TMDB by movie ID.
    """
    return await movie_service.get_movie_details(tmdb_id=tmdb_id, locale=locale)
