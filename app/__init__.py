from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from mongoengine import connect
import os
import app.controllers.auth_controller as auth_controller
import app.controllers.movie_controller as movie_controller
import app.controllers.log_controller as log_controller
import app.controllers.user_controller as user_controller
import app.controllers.movie_rating_controller as movie_rating_controller
import app.controllers.stats_controller as stats_controller
from app.utils.exceptions import AppException
from app.config.cors import get_cors_config

app = FastAPI(
    title="Cinelog API",
)

app.add_middleware(
    CORSMiddleware,
    **get_cors_config()
)

from app.middleware.csrf_middleware import CSRFMiddleware
app.add_middleware(
    CSRFMiddleware, 
    exempt_paths=["/v1/auth/login", "/v1/auth/register", "/docs", "/openapi.json", "/v1/auth/csrf"]
)




mongodb_uri = os.getenv("MONGODB_URI")

if mongodb_uri:
    mongo_client = MongoClient(mongodb_uri)
    mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")
    connect(host=mongodb_uri, db=mongodb_db, uuidRepresentation="standard")
else:
    mongodb_host = os.getenv("MONGODB_HOST", "localhost")
    mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
    mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")

    mongo_client = MongoClient(f"mongodb://{mongodb_host}:{mongodb_port}/{mongodb_db}")
    connect(mongodb_db, host=mongodb_host, port=mongodb_port, uuidRepresentation="standard")


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
