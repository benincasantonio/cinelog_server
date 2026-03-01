import os
from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient
import app.controllers.auth_controller as auth_controller
import app.controllers.movie_controller as movie_controller
import app.controllers.log_controller as log_controller
import app.controllers.user_controller as user_controller
import app.controllers.movie_rating_controller as movie_rating_controller
import app.controllers.stats_controller as stats_controller
from app.middleware.csrf_middleware import CSRFMiddleware
from app.utils.exceptions import AppException
from app.config.cors import get_cors_config
from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.models.user import User
from app.services.tmdb_service import TMDBService


def _get_mongodb_settings() -> tuple[str, str]:
    mongodb_uri = os.getenv("MONGODB_URI")
    mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")

    if mongodb_uri:
        return mongodb_uri, mongodb_db

    mongodb_host = os.getenv("MONGODB_HOST", "localhost")
    mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
    return f"mongodb://{mongodb_host}:{mongodb_port}", mongodb_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    mongodb_uri, mongodb_db = _get_mongodb_settings()
    mongo_client: AsyncMongoClient = AsyncMongoClient(
        mongodb_uri, uuidRepresentation="standard"
    )
    await init_beanie(
        database=mongo_client[mongodb_db],
        document_models=[User, Log, Movie, MovieRating],
    )
    try:
        yield
    finally:
        await TMDBService.aclose_all()
        await mongo_client.close()


app = FastAPI(title="Cinelog API", lifespan=lifespan)

app.add_middleware(
    CSRFMiddleware,
    exempt_paths=[
        "/v1/auth/login",
        "/v1/auth/register",
        "/v1/auth/forgot-password",
        "/v1/auth/reset-password",
        "/v1/auth/csrf",
        "/v1/auth/refresh",
        "/docs",
        "/openapi.json",
    ],
)

app.add_middleware(CORSMiddleware, **get_cors_config())


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Global exception handler for AppException."""
    return JSONResponse(
        status_code=exc.error.error_code,
        content={
            "error_code_name": exc.error.error_code_name,
            "error_code": exc.error.error_code,
            "error_message": exc.error.error_message,
            "error_description": exc.error.error_description,
        },
    )


@app.get("/", tags=["Root"], summary="Cinelog API Root")
def index():
    return "Welcome to the Cinelog API!"


app.include_router(auth_controller.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(movie_controller.router, prefix="/v1/movies", tags=["Movies"])
app.include_router(log_controller.router, prefix="/v1/logs", tags=["Logs"])
app.include_router(user_controller.router, prefix="/v1/users", tags=["Users"])
app.include_router(
    movie_rating_controller.router, prefix="/v1/movie-ratings", tags=["Movie Ratings"]
)
app.include_router(stats_controller.router, prefix="/v1/stats", tags=["Stats"])


def create_app():
    return app
