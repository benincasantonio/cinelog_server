import pytest
from mongoengine import connect, disconnect
import mongomock
from app.models.user import User
from datetime import datetime

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
    User.objects.delete()


def test_user_creation():
    user = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01",
        handle="johndoe"
    )
    user.save()
    assert User.objects.count() == 1


def test_required_fields():
    user = User(
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01",
        handle="johndoe"
    ) 
    with pytest.raises(Exception):
        user.save()


def test_email_uniqueness():
    user1 = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01",
        handle="johndoe"
    )
    user1.save()

    user2 = User(
        firstName="Jane",
        lastName="Smith",
        email="john.doe@example.com",
        password="anotherpassword",
        dateOfBirth="1992-02-02",
        handle="janesmith"
    )
    with pytest.raises(Exception):
        user2.save()

def test_handle_uniqueness():
    user1 = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01",
        handle="johndoe"
    )

    user1.save()

    user2 = User(
        firstName="Jane",
        lastName="Smith",
        email="jane@example.com",
        password="anotherpassword",
        dateOfBirth="1992-02-02",
        handle="johndoe"
    )

    with pytest.raises(Exception):
        user2.save()


def test_created_at_field():
    user = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01",
        handle="johndoe"
    )
    user.save()
    
    assert user.createdAt is not None
    assert isinstance(user.createdAt, datetime)

def test_object_id_field():
    user = User(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        dateOfBirth="1990-01-01",
        handle="johndoe"
    )
    user.save()

    assert user.id is not None
    assert isinstance(user.id, mongomock.ObjectId)