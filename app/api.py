"""FastAPI application construction.

Kept out of ``app/__init__.py`` on purpose. Importing anything under ``app`` executes
the package ``__init__``, so building the ASGI application there forced every consumer
of the package — including the delivery worker, which needs only PostgreSQL and SMTP
settings — to import every controller and satisfy every API secret. The application is
built here and exposed lazily by ``app/__init__.py``.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

import app.controllers.auth_controller as auth_controller
import app.controllers.log_controller as log_controller
import app.controllers.movie_controller as movie_controller
import app.controllers.movie_rating_controller as movie_rating_controller
import app.controllers.notification_controller as notification_controller
import app.controllers.stats_controller as stats_controller
import app.controllers.user_controller as user_controller
from app.config.cors import get_cors_config
from app.config.public_routes import CSRF_EXEMPT_PATHS
from app.config.rate_limiter import limiter
from app.config.redis import get_redis_config
from app.db.postgres import close_postgres_engine, init_postgres_engine
from app.middleware.csrf_middleware import CSRFMiddleware
from app.middleware.rate_limit_session_middleware import RateLimitSessionMiddleware
from app.services.cache_service import CacheService
from app.services.tmdb_service import TMDBService
from app.utils.exceptions_utils import AppException
from app.utils.rate_limit_utils import rate_limit_exceeded_handler
from app.utils.validation_error_utils import sanitize_validation_errors


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_postgres_engine()
    CacheService.initialize(get_redis_config())
    cache = CacheService.get_instance()
    if not await cache.health_check():
        raise RuntimeError("Redis is not reachable — cannot start the application")
    try:
        yield
    finally:
        await CacheService.aclose_all()
        await TMDBService.aclose_all()
        await close_postgres_engine()


app = FastAPI(title="Cinelog API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(RateLimitSessionMiddleware)

app.add_middleware(
    CSRFMiddleware,
    exempt_paths=list(CSRF_EXEMPT_PATHS),
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 422 details without echoing the submitted request values."""
    return JSONResponse(
        status_code=422,
        content={"detail": sanitize_validation_errors(exc.errors())},
    )


@app.get("/", tags=["Root"], summary="Cinelog API Root")
def index():
    return "Welcome to the Cinelog API!"


app.include_router(auth_controller.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(movie_controller.router, prefix="/v1/movies", tags=["Movies"])
app.include_router(log_controller.router, prefix="/v1/logs", tags=["Logs"])
app.include_router(user_controller.router, prefix="/v1/users", tags=["Users"])
app.include_router(movie_rating_controller.router, prefix="/v1/movie-ratings", tags=["Movie Ratings"])
app.include_router(stats_controller.router, prefix="/v1/stats", tags=["Stats"])
app.include_router(notification_controller.router, prefix="/v1/notifications", tags=["Notifications"])


def create_app() -> FastAPI:
    return app
