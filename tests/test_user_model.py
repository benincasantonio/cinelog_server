import pytest
from mongoengine import connect, disconnect
import mongomock
from app.models.user import User

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    # Connect to a test database using the new mongo_client_class parameter
    connect('mongoenginetest', host='localhost', mongo_client_class=mongomock.MongoClient)
    yield
    # Disconnect from the test database
    disconnect()

@pytest.fixture(autouse=True)
def clear_database():
    # Clear the database before each test
    User.objects.delete()


def test_user_creation():
    user = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01"
    )
    user.save()
    assert User.objects.count() == 1


def test_required_fields():
    user = User(
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01"
    )
    with pytest.raises(Exception):
        user.save()


def test_email_uniqueness():
    user1 = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01"
    )
    user1.save()

    user2 = User(
        firstName="Jane",
        lastName="Smith",
        email="john.doe@example.com",
        password="anotherpassword",
        dateOfBirth="1992-02-02"
    )
    with pytest.raises(Exception):
        user2.save()
