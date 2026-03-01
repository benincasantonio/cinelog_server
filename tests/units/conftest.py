import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.models.user import User


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
