from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.params import Depends

from app.dependencies.auth_dependency import auth_dependency
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.services.movie_rating_service import MovieRatingService
from app.services.movie_service import MovieService
from app.schemas.movie_rating_schemas import (
    MovieRatingCreateUpdateRequest,
    MovieRatingResponse,
)
from app.utils.access_token_utils import get_user_id_from_token


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
    _: bool = Depends(auth_dependency),
) -> MovieRatingResponse:
    """
    Create or update a new movie rating entry.

    Requires authentication via Bearer token.
    """

    token = request.headers.get("Authorization")
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return movie_rating_service.create_update_movie_rating(
        user_id=user_id,
        comment=request_body.comment,
        rating=request_body.rating,
        tmdbId=request_body.tmdbId,
    )


@router.get("/{tmdb_id}")
def get_movie_rating(
    tmdb_id: int,
    request: Request,
    user_id: str | None = None,
    _: bool = Depends(auth_dependency),
) -> MovieRatingResponse:
    """
    Get a movie rating entry by TMDB ID.

    If user_id is not provided, it will be extracted from the Bearer token.

    Requires authentication via Bearer token.
    """
    if not user_id:
        token = request.headers.get("Authorization")
        try:
            user_id = get_user_id_from_token(token)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    movie_rating = movie_rating_service.get_movie_ratings_by_tmdb_id(
        user_id=user_id, tmdb_id=tmdb_id
    )

    if not movie_rating:
        raise HTTPException(status_code=404, detail="Movie rating not found")

    return movie_rating
