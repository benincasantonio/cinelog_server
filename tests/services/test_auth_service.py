import pytest
from unittest.mock import Mock, patch
from datetime import date

from app.services.auth_service import AuthService
from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserCreateRequest
from app.schemas.auth_schemas import RegisterRequest, LoginRequest


@pytest.fixture
def mock_user_repository():
    return Mock(spec=UserRepository)


@pytest.fixture
def mock_token_service():
    return Mock()


@pytest.fixture
def auth_service(mock_user_repository, mock_token_service):
    return AuthService(mock_user_repository, mock_token_service)


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


class TestAuthService:
    def test_login_with_valid_credentials(self, auth_service, mock_user_repository, mock_token_service):
        # Arrange
        email = "john.doe@example.com"
        password = "securepassword"
        
        # Mock user retrieval
        mock_user = Mock()
        mock_user.email = email
        mock_user.password = "hashed_password"  # In real implementation this would be hashed
        mock_user_repository.find_user_by_email.return_value = mock_user
        
        # Mock password verification
        with patch('app.services.auth_service.verify_password', return_value=True):
            # Mock token generation
            expected_token = "mock_jwt_token"
            mock_token_service.generate_token.return_value = expected_token
            
            # Act
            result = auth_service.login(email, password)
            
            # Assert
            mock_user_repository.find_user_by_email.assert_called_once_with(email)
            assert result.access_token == expected_token
            assert result.user_id == mock_user.email
            assert result.email == mock_user.email
    
    def test_login_with_invalid_email(self, auth_service, mock_user_repository):
        # Arrange
        email = "nonexistent@example.com"
        password = "password"
        mock_user_repository.find_user_by_email.return_value = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid email or password"):
            auth_service.login(email, password)
        
        # Assert
        mock_user_repository.find_user_by_email.assert_called_once_with(email)
    
    def test_login_with_invalid_password(self, auth_service, mock_user_repository):
        # Arrange
        email = "john.doe@example.com"
        password = "wrongpassword"
        
        mock_user = Mock()
        mock_user.email = email
        mock_user.password = "hashed_correct_password"
        mock_user_repository.find_user_by_email.return_value = mock_user
        
        # Mock password verification
        with patch('app.services.auth_service.verify_password', return_value=False):
            # Act & Assert
            with pytest.raises(ValueError, match="Invalid email or password"):
                auth_service.login(email, password)
            
            # Assert
            mock_user_repository.find_user_by_email.assert_called_once_with(email)
    
    def test_register_new_user(self, auth_service, mock_user_repository, mock_token_service, register_request):
        # Arrange
        mock_user_repository.find_user_by_email.return_value = None
        
        expected_token = "mock_registration_token"
        mock_token_service.generate_token.return_value = expected_token
        
        # Act
        result = auth_service.register(register_request)
        
        # Assert
        mock_user_repository.find_user_by_email.assert_called_once_with(register_request.email)
        mock_user_repository.create_user.assert_called_once_with(request=register_request)
        mock_token_service.generate_token.assert_called_once_with(user_id=register_request.email)
        
        assert result.access_token == expected_token
        assert result.email == register_request.email
        assert result.firstName == register_request.firstName
        assert result.lastName == register_request.lastName
        assert result.handle == register_request.handle
        assert result.user_id == register_request.email
    
    def test_register_existing_user(self, auth_service, mock_user_repository, register_request):
        # Arrange
        mock_user = Mock()
        mock_user.email = register_request.email
        mock_user_repository.find_user_by_email.return_value = mock_user
        
        # Act & Assert
        with pytest.raises(ValueError, match="User with this email already exists"):
            auth_service.register(register_request)
        
        # Assert
        mock_user_repository.find_user_by_email.assert_called_once_with(register_request.email)
        mock_user_repository.create_user.assert_not_called()
