import pytest
from unittest.mock import MagicMock
from app.services.auth_service import AuthService
from app.schemas.auth_schemas import RegisterRequest
from app.schemas.user_schemas import UserCreateRequest
from app.models.user import User
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes
from datetime import date

class TestAuthService:
    @pytest.fixture
    def mock_user_repo(self):
        return MagicMock()

    @pytest.fixture
    def auth_service(self, mock_user_repo):
        return AuthService(user_repository=mock_user_repo)

    def test_register_success(self, auth_service, mock_user_repo):
        request = RegisterRequest(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="password123",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1)
        )
        
        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = None
        
        mock_created_user = User(
            id="507f1f77bcf86cd799439011",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1)
        )
        mock_user_repo.create_user.return_value = mock_created_user

        response = auth_service.register(request)

        assert response.email == "john@example.com"
        mock_user_repo.create_user.assert_called_once()
        
        call_args = mock_user_repo.create_user.call_args[1]
        assert "password_hash" in call_args['request'].model_dump()
        assert call_args['request'].password_hash != "password123"

    def test_login_success(self, auth_service, mock_user_repo):
        email = "john@example.com"
        password = "password123"
        hashed_pw = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW" # bcrypt hash for "password123"
        
        mock_user = User(email=email, password_hash=hashed_pw)
        mock_user_repo.find_user_by_email.return_value = mock_user
        
        # We assume real PasswordService is used (no mocking of static method)
        # So we need a hash that actually matches "password123".
        # The hash above might not be valid for real bcrypt check if salt differs.
        # Let's mock the verify_password just to be safe and isolated.
        with pytest.MonkeyPatch.context() as m:
            from app.services.password_service import PasswordService
            m.setattr(PasswordService, "verify_password", lambda p, h: p == "password123")
            
            user = auth_service.login(email, password)
            assert user == mock_user

    def test_login_invalid_password(self, auth_service, mock_user_repo):
        email = "john@example.com"
        hashed_pw = "hashed_secret"
        
        mock_user = User(email=email, password_hash=hashed_pw)
        mock_user_repo.find_user_by_email.return_value = mock_user
        
        with pytest.MonkeyPatch.context() as m:
            from app.services.password_service import PasswordService
            m.setattr(PasswordService, "verify_password", lambda p, h: False)

            with pytest.raises(AppException) as exc:
                auth_service.login(email, "wrongpassword")
            
            assert exc.value.error.error_code == 401
    
    def test_login_migration_required(self, auth_service, mock_user_repo):
        # User exists (from Firebase) but has no password hash
        mock_user = User(email="old@example.com", password_hash=None)
        mock_user_repo.find_user_by_email.return_value = mock_user
        
        with pytest.raises(AppException) as exc:
            auth_service.login("old@example.com", "anypassword")
            
        assert exc.value.error.error_code == 401
