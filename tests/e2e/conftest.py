"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing.
"""

import os
import httpx
import pytest
import pytest_asyncio
from beanie import init_beanie
from dotenv import load_dotenv
from mongomock_motor import AsyncMongoMockClient
from unittest.mock import patch

from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.models.user import User
from app.schemas.tmdb_schemas import TMDBMovieDetails, TMDBMovieSearchResult
from app.services.tmdb_service import TMDBService

# Load .env file to get TMDB_API_KEY for log tests
load_dotenv()

# Set e2e environment variables BEFORE importing app
os.environ["MONGODB_HOST"] = "localhost"
os.environ["MONGODB_PORT"] = "27018"
os.environ["MONGODB_DB"] = "cinelog_e2e_db"

MONGO_DB = "cinelog_e2e_db"


@pytest.fixture(scope="session")
def mock_mongo_client():
    client = AsyncMongoMockClient()
    yield client
    client.close()


@pytest_asyncio.fixture
async def async_client(mock_mongo_client):
    """Async HTTP client using ASGITransport for direct app testing."""
    import app as app_module

    app_module.AsyncIOMotorClient = lambda *args, **kwargs: mock_mongo_client
    app = app_module.app

    await init_beanie(
        database=mock_mongo_client[MONGO_DB],
        document_models=[User, Log, Movie, MovieRating],
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test"
    ) as client:
        yield client
    await TMDBService.aclose_all()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(mock_mongo_client):
    """Clean all collections before each test."""
    db = mock_mongo_client[MONGO_DB]
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


async def register_and_login(client, user_data: dict) -> dict:
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
