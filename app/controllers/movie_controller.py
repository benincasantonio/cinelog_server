from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.config.rate_limiter import limiter
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.locale_dependency import locale_dependency
from app.dependencies.service_dependency import get_movie_service
from app.schemas.movie_api_schemas import MovieDetails, MovieResolveRequest, MovieResolveResponse, MovieSearchResult
from app.services.movie_service import MovieService

router = APIRouter()


@router.get("/search")
@limiter.limit("20/minute")
async def search_movies(
    request: Request,
    response: Response,
    query: str,
    cursor: str | None = None,
    locale: str = Depends(locale_dependency),
    movie_service: MovieService = Depends(get_movie_service),
) -> MovieSearchResult:
    """
    Search the movie provider one page at a time.

    Catalog films carry their UUID ``id``; other results carry a ``movieRef`` to resolve.
    """
    return await movie_service.search_movie(query=query, locale=locale, cursor=cursor)


@router.post("/resolve")
@limiter.limit("20/minute")
async def resolve_movie(
    request: Request,
    response: Response,
    request_body: MovieResolveRequest,
    user_id: Annotated[UUID, Depends(auth_dependency)],
    movie_service: Annotated[MovieService, Depends(get_movie_service)],
) -> MovieResolveResponse:
    """
    Resolve a search result's movieRef to its Cinelog movie UUID, importing it on first selection.

    Requires authentication via Cookie token.
    """
    return MovieResolveResponse(movie_id=await movie_service.resolve_movie(request_body.movie_ref))


@router.get("/{movie_id}")
async def get_movie_details(
    movie_id: UUID,
    locale: str = Depends(locale_dependency),
    movie_service: MovieService = Depends(get_movie_service),
) -> MovieDetails:
    """
    Get full movie details for a Cinelog movie UUID.
    """
    return await movie_service.get_movie_details(movie_id=movie_id, locale=locale)
