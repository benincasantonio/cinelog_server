import mongomock
import pytest
from bson import ObjectId
from mongoengine import disconnect, connect

from app.models.log import Log


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
    Log.objects.delete()


def test_log_creation():
    log = Log(
        user_id=ObjectId(),
        movie_id=ObjectId(),
        tmdb_id=10,
        date_watched="2023-10-01",
        watched_where="cinema",
        viewing_notes="Great movie!",
        poster_path="/path/to/poster.jpg",
    )

    log.save()

    assert Log.objects.count() == 1
    assert log.id is not None


def test_missing_required_fields():
    log = Log(
        movie_id=ObjectId(),
    )

    with pytest.raises(Exception):
        log.save()


def test_required_fields():
    log = Log(
        user_id=ObjectId(),
        movie_id=ObjectId(),
        tmdb_id=10,
        date_watched="2023-10-01",
        watched_where="cinema",
    )

    log.save()
    assert Log.objects.count() == 1
    assert log.id is not None


def test_wrong_watched_where():
    log = Log(
        user_id=ObjectId(),
        movie_id=ObjectId(),
        tmdb_id=10,
        date_watched="2023-10-01",
        watched_where="unknown",
    )

    with pytest.raises(Exception):
        log.save()
