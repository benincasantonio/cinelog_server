"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing against PostgreSQL.
"""

import os

# Set e2e environment variables BEFORE load_dotenv and any app imports.
# app.config.rate_limiter reads REDIS_URL at import time, so the override
# must be in place before any app module is imported.
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("RATE_LIMIT_HMAC_SECRET", "test-rate-limit-hmac-secret")
os.environ.setdefault("REGISTRATION_VERIFICATION_HMAC_SECRET", "test-registration-verification-hmac-secret")
os.environ.setdefault("CURSOR_PAGINATION_HMAC_SECRET", "test-cursor-pagination-hmac-secret")
os.environ["DATABASE_URL"] = "postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db"

import asyncio  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from unittest.mock import patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import redis.asyncio as aioredis  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.postgres import close_postgres_engine, init_postgres_engine  # noqa: E402
from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult  # noqa: E402
from app.services.cache_service import CacheService  # noqa: E402
from app.services.tmdb_service import TMDBService  # noqa: E402
from app.utils.auth_utils import normalize_email_identifier  # noqa: E402

# Load .env file for remaining env vars (e.g. TMDB_API_KEY, JWT_SECRET_KEY).
# The values set above take precedence because load_dotenv does not overwrite
# existing environment variables by default.
load_dotenv()

POSTGRES_TABLES = ("outbound_messages", "notifications", "logs", "movie_ratings", "movies", "users")


class RegistrationAwareAsyncClient:
    def __init__(self, client: httpx.AsyncClient, registration_codes: dict[str, str]):
        self._client = client
        self._registration_codes = registration_codes

    def __getattr__(self, name: str):
        return getattr(self._client, name)

    async def post(self, url: str, *args, **kwargs):
        request_json = kwargs.get("json")
        if url == "/v1/auth/register" and isinstance(request_json, dict) and "verificationCode" not in request_json:
            email = request_json.get("email")
            if isinstance(email, str) and "@" in email:
                await self._client.post("/v1/auth/register/send-code", json={"email": email})
                code = self._registration_codes.pop(normalize_email_identifier(email), None)
                if code is not None:
                    kwargs["json"] = {**request_json, "verificationCode": code}

        return await self._client.post(url, *args, **kwargs)


def _clear_dependency_caches() -> None:
    from app.dependencies.repository_dependency import (
        get_log_repository,
        get_movie_rating_repository,
        get_movie_repository,
        get_notification_repository,
        get_outbound_message_repository,
        get_stats_repository,
        get_user_repository,
    )
    from app.dependencies.service_dependency import (
        get_auth_service,
        get_log_service,
        get_movie_rating_service,
        get_movie_service,
        get_notification_service,
        get_notification_unit_of_work,
        get_outbound_message_delivery_service,
        get_outbound_message_service,
        get_stats_service,
        get_user_service,
    )

    for provider in (
        get_auth_service,
        get_log_service,
        get_movie_rating_service,
        get_movie_service,
        get_notification_service,
        get_notification_unit_of_work,
        get_outbound_message_service,
        get_outbound_message_delivery_service,
        get_stats_service,
        get_user_service,
        get_log_repository,
        get_movie_rating_repository,
        get_movie_repository,
        get_notification_repository,
        get_outbound_message_repository,
        get_stats_repository,
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
async def postgres_engine():
    engine = init_postgres_engine()
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
async def async_client(postgres_engine):
    """Async HTTP client using ASGITransport for direct app testing."""
    from app.api import app
    from app.config.redis import get_redis_config

    _clear_dependency_caches()

    CacheService.initialize(get_redis_config())
    registration_codes: dict[str, str] = {}

    async def capture_registration_code(self, email: str, code: str, *, expires_at: datetime) -> None:
        assert expires_at > datetime.now(UTC)
        registration_codes[normalize_email_identifier(email)] = code

    async def capture_existing_account_notice(self, email: str) -> None:
        return None

    transport = httpx.ASGITransport(app=app)
    with (
        patch(
            "app.services.outbound_message_service.OutboundMessageService.enqueue_registration_verification",
            capture_registration_code,
        ),
        patch(
            "app.services.outbound_message_service.OutboundMessageService.enqueue_registration_existing_account",
            capture_existing_account_notice,
        ),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            yield RegistrationAwareAsyncClient(client, registration_codes)

    _clear_dependency_caches()
    await CacheService.aclose_all()
    await TMDBService.aclose_all()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(postgres_engine):
    """Clean the database before each test."""
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
