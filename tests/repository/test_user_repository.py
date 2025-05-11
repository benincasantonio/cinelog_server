import pytest
from datetime import date
import mongomock
from mongoengine import connect, disconnect
from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserCreateRequest
from app.models.user import User

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    # Disconnect from any existing connections first
    disconnect()
    # Connect to a test database using mongomock
    connect('mongoenginetest', host='localhost', mongo_client_class=mongomock.MongoClient)
    yield
    # Disconnect from the test database
    disconnect()

@pytest.fixture(autouse=True)
def clear_database():
    # Clear the database before each test
    User.objects.delete()

@pytest.fixture
def user_create_request():
    return UserCreateRequest(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        handle="johndoe",
        dateOfBirth=date(1990, 1, 1)
    )

def test_create_user(user_create_request):
    # Test user creation
    repository = UserRepository()
    user = repository.create_user(user_create_request)
    
    # Assertions
    assert user is not None
    assert user.id is not None
    assert user.firstName == user_create_request.firstName
    assert user.lastName == user_create_request.lastName
    assert user.email == user_create_request.email
    assert User.objects.count() == 1

def test_cannot_create_user_with_same_email():
    # Test creating a user with the same email
    repository = UserRepository()
    user_request1 = UserCreateRequest(
        firstName="Alice",
        lastName="Smith",
        email="alice.smith@example.com",
        password="securepassword",
        handle="alicesmith",
        dateOfBirth=date(1992, 5, 15)
    )

    user_request2 = UserCreateRequest(
        firstName="Bob",
        lastName="Johnson",
        email="alice.smith@example.com",
        password="anotherpassword",
        handle="bobjohnson",
        dateOfBirth=date(1988, 10, 5)
    )

    repository.create_user(user_request1)

    with pytest.raises(Exception):
        repository.create_user(user_request2)

def test_find_user_by_email():
    repository = UserRepository()
    user_request = UserCreateRequest(
        firstName="Jane",
        lastName="Smith",
        email="jane.smith@example.com",
        password="secure123",
        handle="janesmith",
        dateOfBirth=date(1992, 5, 15)
    )
    created_user = repository.create_user(user_request)
    
    # Test finding user by email
    # This method doesn't exist yet, you'll need to implement it
    found_user = repository.find_user_by_email("jane.smith@example.com")
    
    # Assertions
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "jane.smith@example.com"

def test_logical_delete_user():
    # Create a test user first
    repository = UserRepository()
    user_request = UserCreateRequest(
        firstName="Alice",
        lastName="Johnson",
        email="alice.johnson@example.com",
        password="secure456",
        handle="alicej",
        dateOfBirth=date(1985, 3, 20)
    )
    created_user = repository.create_user(user_request)
    
    # Test logical deletion
    # This method doesn't exist yet, you'll need to implement it
    deleted = repository.delete_user(created_user.id)
    
    # Assertions
    assert deleted is True
    
    # User should still exist but have a deleted flag or status
    user = repository.find_user_by_id(created_user.id)
    assert user is not None
    assert user.deleted is True  # Assuming you'll add a deleted flag to the User model

def test_oblivion_user():
    # Create a test user first
    repository = UserRepository()
    user_request = UserCreateRequest(
        firstName="Bob",
        lastName="Williams",
        email="bob.williams@example.com",
        password="secure789",
        handle="bobw",
        dateOfBirth=date(1988, 10, 5)
    )
    created_user = repository.create_user(user_request)
    
    # Test oblivion (permanent deletion or anonymization)
    # This method doesn't exist yet, you'll need to implement it
    success = repository.delete_user_oblivion(created_user.id)

    # oblivion does not delete the user but anonymizes it - search with mongo directly
    user = User.objects(id=created_user.id).first()
    assert success is True
    
    assert user is not None 
    assert user.firstName == "Deleted"
    assert user.lastName == "User"
    assert user.email == ""

def test_find_user_by_handle():
    repository = UserRepository()
    user_request = UserCreateRequest(
        firstName="Charlie",
        lastName="Brown",
        email="test@example.com",
        password="securepassword",
        handle="charliebrown",
        dateOfBirth=date(1990, 1, 1)
    )

    created_user = repository.create_user(user_request)
    found_user = repository.find_user_by_handle("charliebrown")
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.handle == "charliebrown"


def test_find_user_by_email_or_handle():
    repository = UserRepository()
    user_request = UserCreateRequest(
        firstName="David",
        lastName="Smith",
        email="example@example.com",
        password="securepassword",
        handle="david_smith",
        dateOfBirth=date(1990, 1, 1)
    )
    created_user = repository.create_user(user_request)
    found_user_by_email = repository.find_user_by_email_or_handle("example@example.com")
    found_user_by_handle = repository.find_user_by_email_or_handle("david_smith")
    assert found_user_by_email is not None
    assert found_user_by_email.id == created_user.id
    assert found_user_by_email.email == "example@example.com"
    assert found_user_by_handle is not None
    assert found_user_by_handle.id == created_user.id
    assert found_user_by_handle.handle == "david_smith"

    assert found_user_by_email.id == found_user_by_handle.id