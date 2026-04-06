"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing.
"""

import os

# Set e2e environment variables BEFORE load_dotenv and any app imports.
# app.config.rate_limiter reads REDIS_URL at import time, so the override
# must be in place before any app module is imported.
os.environ["MONGODB_HOST"] = "localhost"
os.environ["MONGODB_PORT"] = "27018"
os.environ["MONGODB_DB"] = "cinelog_e2e_db"
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("RATE_LIMIT_HMAC_SECRET", "test-rate-limit-hmac-secret")

import asyncio  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import redis.asyncio as aioredis  # noqa: E402
from beanie import init_beanie  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from pymongo import AsyncMongoClient  # noqa: E402
from unittest.mock import patch  # noqa: E402

from app.models.log import Log  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.models.movie_rating import MovieRating  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult  # noqa: E402
from app.services.cache_service import CacheService  # noqa: E402
from app.services.tmdb_service import TMDBService  # noqa: E402

# Load .env file for remaining env vars (e.g. TMDB_API_KEY, JWT_SECRET_KEY).
# RATE_LIMIT_HMAC_SECRET is set above so auth rate-limit keys stay deterministic.
# os.environ takes precedence over .env values because load_dotenv does NOT
# overwrite existing variables by default.
load_dotenv()

MONGO_DB = "cinelog_e2e_db"


@pytest_asyncio.fixture(autouse=True)
async def flush_redis():
    """Flush Redis before each test to reset rate limit and cache state.

    Flushing before (not after) guarantees a clean slate even if a
    previous test run was interrupted before teardown completed.
    """
    client = aioredis.from_url(os.environ["REDIS_URL"])
    await client.flushdb()
    await client.aclose()
    yield


@pytest_asyncio.fixture
async def mongo_client():
    client: AsyncMongoClient = AsyncMongoClient(
        f"mongodb://{os.environ['MONGODB_HOST']}:{os.environ['MONGODB_PORT']}",
        uuidRepresentation="standard",
    )
    # Wait briefly for the MongoDB container to become ready.
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
async def async_client(mongo_client):
    """Async HTTP client using ASGITransport for direct app testing.

    ASGITransport does not send lifespan events, so the app's startup
    handler (app/__init__.py) never runs. We initialize Beanie and
    CacheService explicitly here instead.
    """
    from app import app
    from app.config.redis import get_redis_config

    await init_beanie(
        database=mongo_client[MONGO_DB],
        document_models=[User, Log, Movie, MovieRating],
    )
    CacheService.initialize(get_redis_config())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test"
    ) as client:
        yield client
    await CacheService.aclose_all()
    await TMDBService.aclose_all()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(mongo_client):
    """Clean all collections before each test."""
    db = mongo_client[MONGO_DB]
    collection_names = await db.list_collection_names()
    for collection_name in collection_names:
        await db.drop_collection(collection_name)
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
