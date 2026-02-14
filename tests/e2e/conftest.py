"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing.
"""

import pytest
import httpx
import os
import requests
from dotenv import load_dotenv
from mongoengine import disconnect, connect

# Load .env file to get TMDB_API_KEY for log tests
load_dotenv()

# Set e2e environment variables BEFORE importing app
os.environ["MONGODB_HOST"] = "localhost"
os.environ["MONGODB_PORT"] = "27018"
os.environ["MONGODB_DB"] = "cinelog_e2e_db"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"
os.environ["FIREBASE_PROJECT_ID"] = "demo-cinelog-e2e"


from app.services.token_service import TokenService

def get_test_token(user_id: str) -> str:
    """
    Generate a local JWT access token for testing.
    """
    return TokenService.create_access_token({"sub": user_id})


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
    
    # Clear Firebase Auth Emulator data
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "demo-cinelog-e2e")
    emulator_host = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    try:
        requests.delete(
            f"http://{emulator_host}/emulator/v1/projects/{project_id}/accounts",
            timeout=5
        )
    except requests.exceptions.RequestException:
        pass  # Emulator might not be running, continue anyway
    
    yield


@pytest.fixture
async def async_client():
    """Async HTTP client using ASGITransport for direct app testing."""
    from app import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

