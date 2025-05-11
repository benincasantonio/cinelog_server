import pytest
from unittest.mock import Mock, patch
from datetime import date
import uuid

from app.services.auth_service import AuthService
from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserCreateRequest
from app.schemas.auth_schemas import RegisterRequest, LoginRequest
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def mock_user_repository():
    return Mock(spec=UserRepository)


@pytest.fixture
def auth_service(mock_user_repository):
    return AuthService(mock_user_repository)


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


@pytest.fixture
def register_request():
    return RegisterRequest(
        firstName="John",
        lastName="Doe",
        email="john.doe@example.com",
        password="securepassword",
        handle="johndoe",
        dateOfBirth=date(1990, 1, 1)
    )


@pytest.fixture
def login_request():
    return LoginRequest(
        emailOrHandle="john.doe@example.com",
        password="securepassword"
    )


class TestAuthService:
    def test_login_with_valid_credentials(self, auth_service, mock_user_repository, login_request):
        # Arrange
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "john.doe@example.com"
        mock_user.firstName = "John"
        mock_user.lastName = "Doe"
        mock_user.handle = "johndoe"
        mock_user.password = "hashed_password"  # In real implementation this would be hashed
        mock_user_repository.find_user_by_email_or_handle.return_value = mock_user
        
        # Mock password verification
        with patch('app.services.auth_service.check_password', return_value=True), \
             patch('app.services.auth_service.generate_access_token', return_value="mock_jwt_token"):
            
            # Act
            result = auth_service.login(login_request)
            
            # Assert
            mock_user_repository.find_user_by_email_or_handle.assert_called_once_with(login_request.emailOrHandle.strip())
            assert result.access_token == "mock_jwt_token"
            assert result.user_id == mock_user.id.__str__()
            assert result.email == mock_user.email
            assert result.firstName == mock_user.firstName
            assert result.lastName == mock_user.lastName
            assert result.handle == mock_user.handle
    
    def test_login_with_invalid_email(self, auth_service, mock_user_repository, login_request):
        # Arrange
        mock_user_repository.find_user_by_email_or_handle.return_value = None
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            auth_service.login(login_request)
        
        # Assert
        assert exc_info.value.error.error_code_name == ErrorCodes.INVALID_EMAIL_OR_PASSWORD.error_code_name
        mock_user_repository.find_user_by_email_or_handle.assert_called_once_with(login_request.emailOrHandle.strip())
    
    def test_login_with_invalid_password(self, auth_service, mock_user_repository, login_request):
        # Arrange
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "john.doe@example.com"
        mock_user.password = "hashed_correct_password"
        mock_user_repository.find_user_by_email_or_handle.return_value = mock_user
        
        # Mock password verification to return False (incorrect password)
        with patch('app.services.auth_service.check_password', return_value=False):
            # Act & Assert
            with pytest.raises(AppException) as exc_info:
                auth_service.login(login_request)
            
            # Assert
            assert exc_info.value.error.error_code_name == ErrorCodes.INVALID_EMAIL_OR_PASSWORD.error_code_name
            mock_user_repository.find_user_by_email_or_handle.assert_called_once_with(login_request.emailOrHandle.strip())
    
    def test_register_new_user(self, auth_service, mock_user_repository, register_request):
        # Arrange
        mock_created_user = Mock()
        mock_created_user.id = uuid.uuid4()
        mock_created_user.email = register_request.email
        mock_created_user.firstName = register_request.firstName
        mock_created_user.lastName = register_request.lastName
        mock_created_user.handle = register_request.handle
        
        mock_user_repository.create_user.return_value = mock_created_user
        
        # Mock token generation
        with patch('app.services.auth_service.hash_password', return_value="hashed_password"), \
             patch('app.services.auth_service.generate_access_token', return_value="mock_jwt_token"):
            
            # Act
            result = auth_service.register(register_request)
            
            # Assert
            mock_user_repository.create_user.assert_called_once()
            assert result.access_token == "mock_jwt_token"
            assert result.email == register_request.email
            assert result.firstName == register_request.firstName
            assert result.lastName == register_request.lastName
            assert result.handle == register_request.handle
            assert result.user_id == mock_created_user.id.__str__()
    
    def test_password_hashing_during_register(self, auth_service, mock_user_repository, register_request):
        # Arrange
        mock_created_user = Mock()
        mock_created_user.id = uuid.uuid4()
        mock_user_repository.create_user.return_value = mock_created_user
        
        # Act
        with patch('app.services.auth_service.hash_password', return_value="hashed_password") as mock_hash, \
             patch('app.services.auth_service.generate_access_token', return_value="mock_token"):
            auth_service.register(register_request)
            
            # Assert
            mock_hash.assert_called_once_with(register_request.password.strip())
