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
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        password="securepassword",
        handle="johndoe",
        date_of_birth=date(1990, 1, 1)
    )

def test_create_user(user_create_request):
    # Test user creation
    repository = UserRepository()
    user = repository.create_user(user_create_request)
    
    # Assertions
    assert user is not None
    assert user.id is not None
    assert user.first_name == user_create_request.first_name
    assert user.last_name == user_create_request.last_name
    assert user.email == user_create_request.email
    assert User.objects.count() == 1

def test_cannot_create_user_with_same_email():
    # Test creating a user with the same email
    repository = UserRepository()
    user_request1 = UserCreateRequest(
        first_name="Alice",
        last_name="Smith",
        email="alice.smith@example.com",
        password="securepassword",
        handle="alicesmith",
        date_of_birth=date(1992, 5, 15)
    )

    user_request2 = UserCreateRequest(
        first_name="Bob",
        last_name="Johnson",
        email="alice.smith@example.com",
        password="anotherpassword",
        handle="bobjohnson",
        date_of_birth=date(1988, 10, 5)
    )

    repository.create_user(user_request1)

    with pytest.raises(Exception):
        repository.create_user(user_request2)

def test_find_user_by_email():
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        password="secure123",
        handle="janesmith",
        date_of_birth=date(1992, 5, 15)
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
        first_name="Alice",
        last_name="Johnson",
        email="alice.johnson@example.com",
        password="secure456",
        handle="alicej",
        date_of_birth=date(1985, 3, 20)
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
        first_name="Bob",
        last_name="Williams",
        email="bob.williams@example.com",
        password="secure789",
        handle="bobw",
        date_of_birth=date(1988, 10, 5)
    )
    created_user = repository.create_user(user_request)
    
    # Test oblivion (permanent deletion or anonymization)
    # This method doesn't exist yet, you'll need to implement it
    success = repository.delete_user_oblivion(created_user.id)

    # oblivion does not delete the user but anonymizes it - search with mongo directly
    user = User.objects(id=created_user.id).first()
    assert success is True
    
    assert user is not None 
    assert user.first_name == "Deleted"
    assert user.last_name == "User"
    assert user.email == ""

def test_find_user_by_handle():
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Charlie",
        last_name="Brown",
        email="test@example.com",
        password="securepassword",
        handle="charliebrown",
        date_of_birth=date(1990, 1, 1)
    )

    created_user = repository.create_user(user_request)
    found_user = repository.find_user_by_handle("charliebrown")
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.handle == "charliebrown"


def test_find_user_by_email_or_handle():
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="David",
        last_name="Smith",
        email="example@example.com",
        password="securepassword",
        handle="david_smith",
        date_of_birth=date(1990, 1, 1)
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


def test_find_user_by_firebase_uid():
    """Test finding a user by Firebase UID."""
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Firebase",
        last_name="User",
        email="firebase.user@example.com",
        password="securepassword",
        handle="firebaseuser",
        date_of_birth=date(1990, 1, 1),
        firebase_uid="firebase_uid_123"
    )
    created_user = repository.create_user(user_request)
    
    found_user = repository.find_user_by_firebase_uid("firebase_uid_123")
    
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.firebase_uid == "firebase_uid_123"


def test_find_user_by_firebase_uid_not_found():
    """Test finding a non-existent user by Firebase UID."""
    repository = UserRepository()
    
    found_user = repository.find_user_by_firebase_uid("non_existent_uid")
    
    assert found_user is None