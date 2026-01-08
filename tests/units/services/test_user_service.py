import pytest
from unittest.mock import Mock, patch, PropertyMock
from datetime import date

from app.services.user_service import UserService
from app.utils.exceptions import AppException


@pytest.fixture
def mock_user_repository():
    return Mock()


@pytest.fixture
def mock_firebase_auth_repository():
    return Mock()


@pytest.fixture
def user_service(mock_user_repository, mock_firebase_auth_repository):
    return UserService(
        user_repository=mock_user_repository,
        firebase_auth_repository=mock_firebase_auth_repository
    )


def create_mock_user(
    user_id="user123",
    first_name="John",
    last_name="Doe",
    email="john@example.com",
    handle="johndoe",
    bio=None,
    date_of_birth=None,
    firebase_uid=None
):
    """Helper to create a mock user with proper attributes."""
    mock_user = Mock()
    mock_user.id = user_id
    mock_user.firstName = first_name
    mock_user.lastName = last_name
    mock_user.email = email
    mock_user.handle = handle
    mock_user.bio = bio
    mock_user.dateOfBirth = date_of_birth or date(1990, 1, 1)
    mock_user.firebaseUid = firebase_uid
    return mock_user


class TestUserService:
    """Tests for UserService."""

    @patch('app.services.user_service.is_firebase_initialized', return_value=True)
    def test_get_user_info_success(self, mock_firebase_init, user_service, mock_user_repository, mock_firebase_auth_repository):
        """Test successful user info retrieval with Firebase data."""
        # Setup mock user
        mock_user = create_mock_user(firebase_uid="firebase_uid_123")
        mock_user_repository.find_user_by_id.return_value = mock_user

        # Setup mock Firebase user
        mock_firebase_user = Mock()
        mock_firebase_user.email = "john@example.com"
        mock_firebase_user.display_name = "John Doe"
        mock_firebase_user.photo_url = "https://example.com/photo.jpg"
        mock_firebase_user.email_verified = True
        mock_firebase_user.disabled = False

        mock_firebase_auth_repository.get_user.return_value = mock_firebase_user

        # Execute
        result = user_service.get_user_info("user123")

        # Verify
        assert result.id == "user123"
        assert result.firstName == "John"
        assert result.lastName == "Doe"
        assert result.firebaseData is not None
        assert result.firebaseData.emailVerified is True

    def test_get_user_info_user_not_found(self, user_service, mock_user_repository):
        """Test get_user_info when user is not found."""
        mock_user_repository.find_user_by_id.return_value = None

        with pytest.raises(AppException):
            user_service.get_user_info("nonexistent_user")

    @patch('app.services.user_service.is_firebase_initialized', return_value=False)
    def test_get_user_info_firebase_not_initialized(self, mock_firebase_init, user_service, mock_user_repository, mock_firebase_auth_repository):
        """Test get_user_info when Firebase is not initialized."""
        mock_user = create_mock_user(firebase_uid="firebase_uid_123")
        mock_user_repository.find_user_by_id.return_value = mock_user

        result = user_service.get_user_info("user123")

        # Firebase data should be None when Firebase is not initialized
        assert result.firebaseData is None
        mock_firebase_auth_repository.get_user.assert_not_called()

    @patch('app.services.user_service.is_firebase_initialized', return_value=True)
    def test_get_user_info_firebase_error(self, mock_firebase_init, user_service, mock_user_repository, mock_firebase_auth_repository):
        """Test get_user_info when Firebase call fails."""
        mock_user = create_mock_user(firebase_uid="firebase_uid_123")
        mock_user_repository.find_user_by_id.return_value = mock_user
        mock_firebase_auth_repository.get_user.side_effect = Exception("Firebase error")

        result = user_service.get_user_info("user123")

        # Should still return user info, just without Firebase data
        assert result.id == "user123"
        assert result.firebaseData is None

    @patch('app.services.user_service.is_firebase_initialized', return_value=True)
    def test_get_user_info_no_firebase_uid(self, mock_firebase_init, user_service, mock_user_repository, mock_firebase_auth_repository):
        """Test get_user_info when user has no Firebase UID."""
        mock_user = create_mock_user(firebase_uid=None)  # No Firebase UID
        mock_user_repository.find_user_by_id.return_value = mock_user

        result = user_service.get_user_info("user123")

        # Firebase data should be None when user has no Firebase UID
        assert result.firebaseData is None
        mock_firebase_auth_repository.get_user.assert_not_called()
