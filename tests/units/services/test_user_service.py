import pytest
from unittest.mock import Mock
from datetime import date

from app.services.user_service import UserService
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def mock_user_repository():
    return Mock()


@pytest.fixture
def user_service(mock_user_repository):
    return UserService(
        user_repository=mock_user_repository
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
    mock_user.first_name = first_name
    mock_user.last_name = last_name
    mock_user.email = email
    mock_user.handle = handle
    mock_user.bio = bio
    mock_user.date_of_birth = date_of_birth or date(1990, 1, 1)
    mock_user.firebase_uid = firebase_uid
    return mock_user


class TestUserService:
    """Tests for UserService."""

    def test_get_user_info_success(self, user_service, mock_user_repository):
        """Test successful user info retrieval."""
        # Setup mock user
        mock_user = create_mock_user()
        mock_user_repository.find_user_by_id.return_value = mock_user

        # Execute
        result = user_service.get_user_info("user123")

        # Verify
        assert result.id == "user123"
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        assert result.firebase_uid is None
        mock_user_repository.find_user_by_id.assert_called_once_with("user123")

    def test_get_user_info_user_not_found(self, user_service, mock_user_repository):
        """Test get_user_info when user is not found."""
        mock_user_repository.find_user_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            user_service.get_user_info("nonexistent_user")
            
        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code
