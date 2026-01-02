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
    Create a new movie rating entry.

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
        tmdb_id=request_body.tmdbId,
    )
