from fastapi import APIRouter, Request

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import LoginRequest, RegisterRequest, RegisterResponse, LoginResponse
from app.services.auth_service import AuthService
from app.services.tmdb_service import TMDBService
from app.utils.exceptions import AppException
from os import getenv

router = APIRouter()

TMDB_API_KEY = getenv("TMDB_API_KEY")
print(TMDB_API_KEY)
tmdb_service = TMDBService(api_key=TMDB_API_KEY)


@router.get("/search")
def search_movies(query: str):
    """
    Search for movies using TMDB API.
    """
    try:
        return tmdb_service.search_movie(query=query)
    except AppException as e:
        raise e