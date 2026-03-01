import pytest
from pymongo.errors import DuplicateKeyError

from app.models.movie import Movie


@pytest.mark.asyncio
async def test_movie_creation(beanie_test_db):
    movie = Movie(tmdb_id=123456, title="Inception")
    await movie.insert()
    assert await Movie.find_all().count() == 1


@pytest.mark.asyncio
async def test_required_fields():
    with pytest.raises(Exception):
        Movie(title="Inception")


@pytest.mark.asyncio
async def test_tmdb_id_uniqueness(beanie_test_db):
    movie1 = Movie(tmdb_id=123456, title="Inception")
    await movie1.insert()

    movie2 = Movie(tmdb_id=123456, title="The Matrix")
    with pytest.raises(DuplicateKeyError):
        await movie2.insert()
