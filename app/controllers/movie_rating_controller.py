from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request, Response, status

from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_movie_rating_service
from app.schemas.movie_rating_schemas import (
    MovieRatingCreateUpdateRequest,
    MovieRatingResponse,
)
from app.services.movie_rating_service import MovieRatingService

router = APIRouter()


@router.post("/")
async def create_movie_rating(
    request_body: MovieRatingCreateUpdateRequest,
    request: Request,
    user_id: Annotated[PydanticObjectId, Depends(auth_dependency)],
    movie_rating_service: Annotated[MovieRatingService, Depends(get_movie_rating_service)],
) -> MovieRatingResponse:
    """
    Create or update a new movie rating entry.

    Requires authentication via Cookie token.
    """
    return await movie_rating_service.create_update_movie_rating(
        user_id=user_id,
        comment=request_body.comment,
        rating=request_body.rating,
        tmdb_id=request_body.tmdb_id,
    )


@router.get("/{tmdb_id}", response_model=None)
async def get_movie_rating(
    tmdb_id: int,
    current_user_id: Annotated[PydanticObjectId, Depends(auth_dependency)],
    movie_rating_service: Annotated[MovieRatingService, Depends(get_movie_rating_service)],
) -> MovieRatingResponse | Response:
    """
    Get a movie rating entry by TMDB ID.

    Requires authentication via Cookie token.
    """
    movie_rating = await movie_rating_service.get_movie_ratings_by_tmdb_id(
        user_id=current_user_id,
        tmdb_id=tmdb_id,
    )

    if not movie_rating:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return movie_rating
