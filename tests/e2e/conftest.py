"""
E2E test fixtures for the cinelog_server application.
Uses httpx ASGITransport for direct FastAPI testing.
"""

import pytest
import httpx
import os
import requests
from mongoengine import disconnect, connect

# Set e2e environment variables BEFORE importing app
os.environ["MONGODB_HOST"] = "localhost"
os.environ["MONGODB_PORT"] = "27018"
os.environ["MONGODB_DB"] = "cinelog_e2e_db"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"
os.environ["FIREBASE_PROJECT_ID"] = "demo-cinelog-e2e"


@pytest.fixture(scope="session")
def e2e_mongo():
    """Connect to e2e MongoDB container."""
    disconnect(alias="default")
    connect(
        db="cinelog_e2e_db",
        host="localhost",
        port=27018,
        alias="default"
    )
    yield
    disconnect(alias="default")


@pytest.fixture(autouse=True)
def clean_db(e2e_mongo):
    """Clean all collections and Firebase emulator data before each test."""
    from app.models.user import User
    User.objects.delete()
    
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

