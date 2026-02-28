import pytest
from mongoengine import disconnect, connect
import mongomock

from app.models.movie import Movie


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    # Disconnect from any existing connections first
    disconnect()
    # Connect to a test database using the new mongo_client_class parameter
    connect(
        "mongoenginetest",
        host="localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    # Disconnect from the test database
    disconnect()


@pytest.fixture(autouse=True)
def clear_database():
    # Clear the database before each test
    Movie.objects.delete()


def test_movie_creation():
    movie = Movie(tmdb_id="123456", title="Inception")
    movie.save()
    assert Movie.objects.count() == 1


def test_required_fields():
    movie = Movie(title="Inception")
    with pytest.raises(Exception):
        movie.save()


def test_tmdb_id_uniqueness():
    movie1 = Movie(tmdb_id="123456", title="Inception")
    movie1.save()

    movie2 = Movie(tmdb_id="123456", title="The Matrix")
    with pytest.raises(Exception):
        movie2.save()
