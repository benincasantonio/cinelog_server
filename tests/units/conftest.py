import pytest
import pytest_asyncio
from beanie import init_beanie
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from mongomock_motor import AsyncMongoMockClient

import app.config.rate_limiter as rate_limiter_module
from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.models.user import User


@pytest.fixture(autouse=True)
def use_memory_storage_for_rate_limiter():
    """
    Swap the global rate limiter's Redis storage with in-memory storage for
    all unit tests. This prevents tests from requiring a live Redis connection.
    Rate limit counts are reset per test via a fresh MemoryStorage instance.
    """
    memory_storage = MemoryStorage()
    original_storage = rate_limiter_module.limiter._storage
    original_limiter = rate_limiter_module.limiter._limiter

    rate_limiter_module.limiter._storage = memory_storage
    rate_limiter_module.limiter._limiter = FixedWindowRateLimiter(memory_storage)

    yield

    rate_limiter_module.limiter._storage = original_storage
    rate_limiter_module.limiter._limiter = original_limiter


@pytest_asyncio.fixture
async def beanie_test_db():
    client = AsyncMongoMockClient()
    db = client["mongoenginetest"]
    await init_beanie(database=db, document_models=[User, Movie, Log, MovieRating])
    yield db
    collection_names = await db.list_collection_names()
    for collection_name in collection_names:
        await db.drop_collection(collection_name)
    client.close()
