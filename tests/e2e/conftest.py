"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing against the selected backend.
"""

import os

E2E_BACKEND = os.environ.get("E2E_BACKEND", "mongo").strip().lower()
if E2E_BACKEND not in {"mongo", "postgres"}:
    raise RuntimeError(f"Unsupported E2E_BACKEND={E2E_BACKEND!r}. Expected 'mongo' or 'postgres'.")

# Set e2e environment variables BEFORE load_dotenv and any app imports.
# app.config.rate_limiter reads REDIS_URL at import time, so the override
# must be in place before any app module is imported.
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("RATE_LIMIT_HMAC_SECRET", "test-rate-limit-hmac-secret")

if E2E_BACKEND == "postgres":
    os.environ["DB_BACKEND"] = "postgres"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db"
else:
    os.environ["MONGODB_HOST"] = "localhost"
    os.environ["MONGODB_PORT"] = "27018"
    os.environ["MONGODB_DB"] = "cinelog_e2e_db"
    os.environ["DB_BACKEND"] = "mongo"

import asyncio  # noqa: E402
from unittest.mock import patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import redis.asyncio as aioredis  # noqa: E402
from beanie import init_beanie  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from pymongo import AsyncMongoClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.postgres import close_postgres_engine, init_postgres_engine  # noqa: E402
from app.models.log import Log  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.models.movie_rating import MovieRating  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult  # noqa: E402
from app.services.cache_service import CacheService  # noqa: E402
from app.services.tmdb_service import TMDBService  # noqa: E402

# Load .env file for remaining env vars (e.g. TMDB_API_KEY, JWT_SECRET_KEY).
# The values set above take precedence because load_dotenv does not overwrite
# existing environment variables by default.
load_dotenv()

MONGO_DB = "cinelog_e2e_db"
POSTGRES_TABLES = ("logs", "movie_ratings", "movies", "users")


def _clear_dependency_caches() -> None:
    from app.dependencies.repository_dependency import (
        get_log_repository,
        get_movie_rating_repository,
        get_movie_repository,
        get_user_repository,
    )
    from app.dependencies.service_dependency import (
        get_auth_service,
        get_log_service,
        get_movie_rating_service,
        get_movie_service,
        get_stats_service,
        get_user_service,
    )

    for provider in (
        get_auth_service,
        get_log_service,
        get_movie_rating_service,
        get_movie_service,
        get_stats_service,
        get_user_service,
        get_log_repository,
        get_movie_rating_repository,
        get_movie_repository,
        get_user_repository,
    ):
        provider.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def flush_redis():
    """Flush Redis before each test to reset rate limit and cache state."""
    client = aioredis.from_url(os.environ["REDIS_URL"])
    await client.flushdb()
    await client.aclose()
    yield


@pytest_asyncio.fixture
async def mongo_client():
    if E2E_BACKEND != "mongo":
        yield None
        return

    client: AsyncMongoClient = AsyncMongoClient(
        f"mongodb://{os.environ['MONGODB_HOST']}:{os.environ['MONGODB_PORT']}",
        uuidRepresentation="standard",
    )
    for _ in range(30):
        try:
            await client.admin.command("ping")
            break
        except Exception:
            await asyncio.sleep(0.25)
    else:
        raise RuntimeError("MongoDB for E2E tests is not reachable on port 27018")

    yield client
    await client.close()


@pytest_asyncio.fixture
async def postgres_engine():
    if E2E_BACKEND != "postgres":
        yield None
        return

    engine = init_postgres_engine(required=True)
    if engine is None:
        raise RuntimeError("PostgreSQL engine failed to initialize for e2e tests.")

    for _ in range(30):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            break
        except Exception:
            await asyncio.sleep(0.25)
    else:
        raise RuntimeError("PostgreSQL for E2E tests is not reachable on port 5433")

    yield engine
    await close_postgres_engine()


@pytest_asyncio.fixture
async def async_client(mongo_client, postgres_engine):
    """Async HTTP client using ASGITransport for direct app testing."""
    from app import app
    from app.config.redis import get_redis_config

    _clear_dependency_caches()

    if E2E_BACKEND == "mongo":
        await init_beanie(
            database=mongo_client[MONGO_DB],
            document_models=[User, Log, Movie, MovieRating],
        )
    else:
        init_postgres_engine(required=True)

    CacheService.initialize(get_redis_config())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield client

    _clear_dependency_caches()
    await CacheService.aclose_all()
    await TMDBService.aclose_all()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(mongo_client, postgres_engine):
    """Clean the active database before each test."""
    if E2E_BACKEND == "mongo":
        db = mongo_client[MONGO_DB]
        collection_names = await db.list_collection_names()
        for collection_name in collection_names:
            await db.drop_collection(collection_name)
    else:
        async with postgres_engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {', '.join(POSTGRES_TABLES)} RESTART IDENTITY CASCADE"))

    yield


@pytest.fixture(autouse=True)
def mock_tmdb_requests():
    async def fake_get_movie_details(self, tmdb_id: int) -> TMDBMovieDetails:
        return TMDBMovieDetails(
            id=tmdb_id,
            title=f"Movie {tmdb_id}",
            original_title=f"Movie {tmdb_id}",
            overview="Mocked movie details",
            release_date="2024-01-01",
            poster_path="/poster.jpg",
            backdrop_path="/backdrop.jpg",
            vote_average=7.5,
            vote_count=1000,
            runtime=120,
            budget=50000000,
            revenue=100000000,
            status="Released",
            tagline="Mocked tagline",
            homepage=None,
            imdb_id=None,
            original_language="en",
            popularity=50.5,
            adult=False,
            genres=[],
            production_companies=[],
            production_countries=[],
            spoken_languages=[],
        )

    async def fake_search_movie(self, query: str) -> TMDBMovieSearchResult:
        return TMDBMovieSearchResult(page=1, total_results=0, total_pages=0, results=[])

    with (
        patch(
            "app.services.tmdb_service.TMDBService.get_movie_details",
            fake_get_movie_details,
        ),
        patch("app.services.tmdb_service.TMDBService.search_movie", fake_search_movie),
    ):
        yield


async def register(client, user_data: dict):
    """Helper: Register a user."""
    reg_resp = await client.post("/v1/auth/register", json=user_data)
    assert reg_resp.status_code == 201
    return reg_resp.json()


async def register_and_login(client, user_data: dict):
    """
    Helper: Register a user, then login to get auth cookies + CSRF token.
    Returns the login response JSON (includes csrfToken).
    """
    reg_resp = await client.post("/v1/auth/register", json=user_data)
    assert reg_resp.status_code == 201

    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert login_resp.status_code == 200
    return login_resp.json()
