from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.auth_dependency import auth_dependency
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.services.movie_rating_service import MovieRatingService
from app.services.movie_service import MovieService
from app.schemas.movie_rating_schemas import (
    MovieRatingCreateUpdateRequest,
    MovieRatingResponse,
)


router = APIRouter()

movie_rating_repository = MovieRatingRepository()
movie_repository = MovieRepository()
movie_service = MovieService(movie_repository)

movie_rating_service = MovieRatingService(
    movie_rating_repository=movie_rating_repository, movie_service=movie_service
)


@router.post("/")
def create_movie_rating(
    request_body: MovieRatingCreateUpdateRequest,
    request: Request,
    user_id: Annotated[str, Depends(auth_dependency)],
) -> MovieRatingResponse:
    """
    Create or update a new movie rating entry.

    Requires authentication via Cookie token.
    """
    return movie_rating_service.create_update_movie_rating(
        user_id=user_id,
        comment=request_body.comment,
        rating=request_body.rating,
        tmdb_id=request_body.tmdb_id,
    )


@router.get("/{tmdb_id}")
def get_movie_rating(
    tmdb_id: int,
    current_user_id: Annotated[str, Depends(auth_dependency)],
    user_id: str | None = None,
) -> MovieRatingResponse:
    """
    Get a movie rating entry by TMDB ID.

    If user_id is not provided, it will use the current authenticated user's ID.

    Requires authentication via Cookie token.
    """
    target_user_id = user_id if user_id else current_user_id

    movie_rating = movie_rating_service.get_movie_ratings_by_tmdb_id(
        user_id=target_user_id, tmdb_id=tmdb_id
    )

    if not movie_rating:
        raise HTTPException(status_code=404, detail="Movie rating not found")

    return movie_rating
