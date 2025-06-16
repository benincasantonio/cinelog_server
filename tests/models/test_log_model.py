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
    connect('mongoenginetest', host='localhost', mongo_client_class=mongomock.MongoClient)
    yield
    # Disconnect from the test database
    disconnect()

@pytest.fixture(autouse=True)
def clear_database():
    # Clear the database before each test
    Log.objects.delete()


def test_log_creation():
    log = Log(
        movieId=ObjectId(),
        tmdbId = 10,
        dateWatched="2023-10-01",
        watchedWhere="cinema",
        comment="Great movie!",
        rating=8,
        posterPath="/path/to/poster.jpg",
    )

    log.save()

    assert Log.objects.count() == 1
    assert log.id is not None


def test_missing_required_fields():
    log = Log(
        movieId=ObjectId(),
    )

    with pytest.raises(Exception):
        log.save()



def test_required_fields():
    log = Log(
        movieId=ObjectId(),
        tmdbId=10,
        dateWatched="2023-10-01",
        watchedWhere="cinema",
    )

    log.save()
    assert Log.objects.count() == 1
    assert log.id is not None


def test_wrong_watched_where():
    log = Log(
        movieId=ObjectId(),
        tmdbId=10,
        dateWatched="2023-10-01",
        watchedWhere="unknown",
    )

    with pytest.raises(Exception):
        log.save()


def test_wrong_rating():
    log = Log(
        movieId=(ObjectId()),
        tmdbId=10,
        dateWatched="2023-10-01",
        watchedWhere="cinema",
        rating=11,  # Rating should be between 1 and 10
    )

    with pytest.raises(Exception):
        log.save()
