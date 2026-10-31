from typing import Annotated
from uuid import UUID

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
    user_id: Annotated[UUID, Depends(auth_dependency)],
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
        movie_id=request_body.movie_id,
    )


@router.get("/{movie_id}", response_model=None)
async def get_movie_rating(
    movie_id: UUID,
    current_user_id: Annotated[UUID, Depends(auth_dependency)],
    movie_rating_service: Annotated[MovieRatingService, Depends(get_movie_rating_service)],
) -> MovieRatingResponse | Response:
    """
    Get the caller's rating for a Cinelog movie UUID; 204 when the movie has no rating.

    Requires authentication via Cookie token.
    """
    movie_rating = await movie_rating_service.get_movie_rating(
        user_id=current_user_id,
        movie_id=movie_id,
    )

    if not movie_rating:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return movie_rating
