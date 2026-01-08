import pytest
from unittest.mock import Mock, patch
from datetime import date
import uuid

from app.services.auth_service import AuthService
from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository
from app.schemas.user_schemas import UserCreateRequest
from app.schemas.auth_schemas import RegisterRequest
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def mock_user_repository():
    return Mock(spec=UserRepository)


@pytest.fixture
def mock_firebase_auth_repository():
    return Mock(spec=FirebaseAuthRepository)


@pytest.fixture
def auth_service(mock_user_repository, mock_firebase_auth_repository):
    return AuthService(mock_user_repository, mock_firebase_auth_repository)


@pytest.fixture
def user_create_request():
    return UserCreateRequest(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        handle="johndoe",
        date_of_birth=date(1990, 1, 1),
        firebase_uid="test_firebase_uid"
    )


@pytest.fixture
def register_request():
    return RegisterRequest(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        password="securepassword",
        handle="johndoe",
        date_of_birth=date(1990, 1, 1)
    )


class TestAuthService:
    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_new_user(self, mock_is_firebase_init, auth_service, mock_user_repository, mock_firebase_auth_repository, register_request):
        # Arrange
        mock_created_user = Mock()
        mock_created_user.id = uuid.uuid4()
        mock_created_user.email = register_request.email
        mock_created_user.first_name = register_request.first_name
        mock_created_user.last_name = register_request.last_name
        mock_created_user.handle = register_request.handle
        mock_created_user.bio = None
        
        mock_firebase_user = Mock()
        mock_firebase_user.uid = "firebase_test_uid"
        
        mock_user_repository.find_user_by_email.return_value = None
        mock_user_repository.find_user_by_handle.return_value = None
        mock_firebase_auth_repository.create_user.return_value = mock_firebase_user
        mock_user_repository.create_user.return_value = mock_created_user
        
        # Act
        result = auth_service.register(register_request)
        
        # Assert
        mock_user_repository.find_user_by_email.assert_called_once()
        mock_user_repository.find_user_by_handle.assert_called_once()
        mock_firebase_auth_repository.create_user.assert_called_once()
        mock_user_repository.create_user.assert_called_once()
        assert result.email == register_request.email
        assert result.first_name == register_request.first_name
        assert result.last_name == register_request.last_name
        assert result.handle == register_request.handle
        assert result.user_id == mock_created_user.id.__str__()

    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_email_already_exists(self, mock_is_firebase_init, auth_service, mock_user_repository, register_request):
        # Arrange
        mock_user_repository.find_user_by_email.return_value = Mock()  # User exists
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            auth_service.register(register_request)
        
        # Assert
        assert exc_info.value.error.error_code_name == ErrorCodes.EMAIL_ALREADY_EXISTS.error_code_name

    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_handle_already_exists(self, mock_is_firebase_init, auth_service, mock_user_repository, register_request):
        # Arrange
        mock_user_repository.find_user_by_email.return_value = None
        mock_user_repository.find_user_by_handle.return_value = Mock()  # Handle exists
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            auth_service.register(register_request)
        
        # Assert
        assert exc_info.value.error.error_code_name == ErrorCodes.HANDLE_ALREADY_TAKEN.error_code_name

    def test_register_firebase_not_initialized(self, auth_service, register_request):
        # Arrange
        with patch('app.services.auth_service.is_firebase_initialized', return_value=False):
            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                auth_service.register(register_request)
            
            assert str(exc_info.value) == "Firebase Admin SDK is not initialized"

    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_firebase_email_already_exists(self, mock_is_firebase_init, auth_service, mock_user_repository, mock_firebase_auth_repository, register_request):
        """Test register raises AppException when Firebase reports email already exists."""
        from firebase_admin import auth
        
        # Arrange
        mock_user_repository.find_user_by_email.return_value = None
        mock_user_repository.find_user_by_handle.return_value = None
        mock_firebase_auth_repository.create_user.side_effect = auth.EmailAlreadyExistsError(
            message="Email already exists",
            cause=None,
            http_response=None
        )
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            auth_service.register(register_request)
        
        assert exc_info.value.error.error_code_name == ErrorCodes.EMAIL_ALREADY_EXISTS.error_code_name

    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_firebase_generic_exception(self, mock_is_firebase_init, auth_service, mock_user_repository, mock_firebase_auth_repository, register_request):
        """Test register raises AppException when Firebase throws generic exception."""
        # Arrange
        mock_user_repository.find_user_by_email.return_value = None
        mock_user_repository.find_user_by_handle.return_value = None
        mock_firebase_auth_repository.create_user.side_effect = Exception("Firebase error")
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            auth_service.register(register_request)
        
        assert exc_info.value.error.error_code_name == ErrorCodes.ERROR_CREATING_USER.error_code_name

    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_mongodb_failure_triggers_firebase_rollback(self, mock_is_firebase_init, auth_service, mock_user_repository, mock_firebase_auth_repository, register_request):
        """Test register rolls back Firebase user when MongoDB creation fails."""
        # Arrange
        mock_firebase_user = Mock()
        mock_firebase_user.uid = "firebase_test_uid"
        
        mock_user_repository.find_user_by_email.return_value = None
        mock_user_repository.find_user_by_handle.return_value = None
        mock_firebase_auth_repository.create_user.return_value = mock_firebase_user
        mock_user_repository.create_user.side_effect = Exception("MongoDB error")
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            auth_service.register(register_request)
        
        assert exc_info.value.error.error_code_name == ErrorCodes.ERROR_CREATING_USER.error_code_name
        # Verify rollback was attempted
        mock_firebase_auth_repository.delete_user.assert_called_once_with("firebase_test_uid")

    @patch('app.services.auth_service.is_firebase_initialized', return_value=True)
    def test_register_mongodb_failure_rollback_also_fails(self, mock_is_firebase_init, auth_service, mock_user_repository, mock_firebase_auth_repository, register_request):
        """Test register handles rollback failure gracefully."""
        # Arrange
        mock_firebase_user = Mock()
        mock_firebase_user.uid = "firebase_test_uid"
        
        mock_user_repository.find_user_by_email.return_value = None
        mock_user_repository.find_user_by_handle.return_value = None
        mock_firebase_auth_repository.create_user.return_value = mock_firebase_user
        mock_user_repository.create_user.side_effect = Exception("MongoDB error")
        mock_firebase_auth_repository.delete_user.side_effect = Exception("Rollback failed")
        
        # Act & Assert - Should still raise the original error, not the rollback error
        with pytest.raises(AppException) as exc_info:
            auth_service.register(register_request)
        
        assert exc_info.value.error.error_code_name == ErrorCodes.ERROR_CREATING_USER.error_code_name

