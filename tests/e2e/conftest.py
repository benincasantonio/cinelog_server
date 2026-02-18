"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing.
"""

import pytest
import httpx
import os
from dotenv import load_dotenv
from mongoengine import disconnect, connect

# Load .env file to get TMDB_API_KEY for log tests
load_dotenv()

# Set e2e environment variables BEFORE importing app
os.environ["MONGODB_HOST"] = "localhost"
os.environ["MONGODB_PORT"] = "27018"
os.environ["MONGODB_DB"] = "cinelog_e2e_db"
os.environ["MONGODB_DB"] = "cinelog_e2e_db"





@pytest.fixture(scope="session", autouse=True)
def e2e_mongo():
    """Connect to e2e MongoDB container."""
    try:
        disconnect(alias="default")
        connect(
            db="cinelog_e2e_db",
            host="localhost",
            port=27018,
            alias="default",
            uuidRepresentation="standard"
        )
    except Exception as e:
        import warnings
        warnings.warn(f"Could not establish MongoDB connection: {e}")
    yield
    try:
        disconnect(alias="default")
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_db(e2e_mongo):
    """Clean all collections and Firebase emulator data before each test."""
    try:
        from app.models.user import User
        from app.models.log import Log
        from app.models.movie import Movie
        User.objects.delete()
        Log.objects.delete()
        Movie.objects.delete()
    except Exception as e:
        import warnings
        warnings.warn(f"Could not clean MongoDB collections: {e}")
    
    
    yield


@pytest.fixture
async def async_client():
    """Async HTTP client using ASGITransport for direct app testing."""
    from app import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield client


async def register_and_login(client, user_data: dict) -> dict:
    """
    Helper: Register a user, then login to get auth cookies + CSRF token.
    Returns the login response JSON (includes csrfToken).
    """
    reg_resp = await client.post("/v1/auth/register", json=user_data)
    assert reg_resp.status_code == 201

    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]}
    )
    assert login_resp.status_code == 200
    return login_resp.json()
