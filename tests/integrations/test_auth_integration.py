"""
Integration tests for auth endpoints.
Tests controller + service + FirebaseAuthRepository layers with mocked firebase_admin.auth.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import uuid

from app import app
from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository
from app.services.auth_service import AuthService
from app.utils.error_codes import ErrorCodes
from firebase_admin import auth


class TestAuthIntegration:
    """
    Integration tests for registration endpoint (POST /v1/auth/register).
    
    Tests: Controller → Service → FirebaseAuthRepository
    Mocks: UserRepository (MongoDB) and firebase_admin.auth (Firebase SDK)
    """

    @pytest.fixture
    def mock_user_repository(self):
        """Mock UserRepository for MongoDB operations."""
        return Mock(spec=UserRepository)

    @pytest.fixture
    def real_firebase_auth_repository(self):
        """Real FirebaseAuthRepository - will use mocked firebase_admin.auth."""
        return FirebaseAuthRepository()

    @pytest.fixture
    def client_with_mocks(self, mock_user_repository, real_firebase_auth_repository):
        """
        Test client with:
        - Mocked UserRepository (no MongoDB needed)
        - Real FirebaseAuthRepository (but firebase_admin.auth is mocked)
        """
        auth_service = AuthService(mock_user_repository, real_firebase_auth_repository)

        with patch('app.controllers.auth_controller.user_repository', mock_user_repository), \
             patch('app.controllers.auth_controller.firebase_auth_repository', real_firebase_auth_repository), \
             patch('app.controllers.auth_controller.auth_service', auth_service), \
             patch('app.integrations.firebase.is_firebase_initialized', return_value=True), \
             patch('app.services.auth_service.is_firebase_initialized', return_value=True), \
             patch('app.repository.firebase_auth_repository.is_firebase_initialized', return_value=True):
            yield TestClient(app), mock_user_repository

    @pytest.fixture
    def valid_register_payload(self):
        """Valid registration request payload."""
        return {
            "email": "test@example.com",
            "password": "securepassword123",
            "firstName": "John",
            "lastName": "Doe",
            "handle": "johndoe",
            "dateOfBirth": "1990-01-01"
        }

    @patch('app.repository.firebase_auth_repository.auth')
    def test_register_success(self, mock_firebase_auth, client_with_mocks, valid_register_payload):
        """Test successful registration through controller → service → repository."""
        client, mock_user_repo = client_with_mocks

        # Setup mocks - no existing user in MongoDB
        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = None

        # Firebase create_user returns a UserRecord
        mock_firebase_user = MagicMock()
        mock_firebase_user.uid = "firebase_uid_123"
        mock_firebase_auth.create_user.return_value = mock_firebase_user

        # MongoDB user creation succeeds
        mock_created_user = Mock()
        mock_created_user.id = uuid.uuid4()
        mock_created_user.email = valid_register_payload["email"]
        mock_created_user.first_name = valid_register_payload["firstName"]
        mock_created_user.last_name = valid_register_payload["lastName"]
        mock_created_user.handle = valid_register_payload["handle"]
        mock_created_user.bio = None
        mock_user_repo.create_user.return_value = mock_created_user

        # Act
        response = client.post("/v1/auth/register", json=valid_register_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == valid_register_payload["email"]
        assert data["firstName"] == valid_register_payload["firstName"]
        assert data["lastName"] == valid_register_payload["lastName"]
        assert data["handle"] == valid_register_payload["handle"]
        assert "userId" in data

        # Verify the full chain was called
        mock_user_repo.find_user_by_email.assert_called_once()
        mock_user_repo.find_user_by_handle.assert_called_once()
        mock_firebase_auth.create_user.assert_called_once()  # Real repository called firebase
        mock_user_repo.create_user.assert_called_once()

    @patch('app.repository.firebase_auth_repository.auth')
    def test_register_duplicate_email(self, mock_firebase_auth, client_with_mocks, valid_register_payload):
        """Test registration fails when email already exists in MongoDB."""
        client, mock_user_repo = client_with_mocks

        # Email exists in MongoDB
        mock_user_repo.find_user_by_email.return_value = Mock()

        response = client.post("/v1/auth/register", json=valid_register_payload)

        assert response.status_code == 409
        assert response.json()["error_code_name"] == ErrorCodes.EMAIL_ALREADY_EXISTS.error_code_name

        # Firebase should NOT be called (early return)
        mock_firebase_auth.create_user.assert_not_called()

    @patch('app.repository.firebase_auth_repository.auth')
    def test_register_duplicate_handle(self, mock_firebase_auth, client_with_mocks, valid_register_payload):
        """Test registration fails when handle already exists."""
        client, mock_user_repo = client_with_mocks

        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = Mock()  # Handle exists

        response = client.post("/v1/auth/register", json=valid_register_payload)

        assert response.status_code == 409
        assert response.json()["error_code_name"] == ErrorCodes.HANDLE_ALREADY_TAKEN.error_code_name

        # Firebase should NOT be called
        mock_firebase_auth.create_user.assert_not_called()

    @patch('app.repository.firebase_auth_repository.auth')
    def test_register_firebase_email_already_exists(self, mock_firebase_auth, client_with_mocks, valid_register_payload):
        """Test registration fails when email exists in Firebase (not MongoDB)."""
        client, mock_user_repo = client_with_mocks

        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = None
        
        # Firebase raises EmailAlreadyExistsError
        mock_firebase_auth.create_user.side_effect = auth.EmailAlreadyExistsError(
            message="Email already exists",
            cause=None,
            http_response=None
        )

        response = client.post("/v1/auth/register", json=valid_register_payload)

        assert response.status_code == 409
        assert response.json()["error_code_name"] == ErrorCodes.EMAIL_ALREADY_EXISTS.error_code_name

    @patch('app.repository.firebase_auth_repository.auth')
    def test_register_mongodb_failure_triggers_rollback(self, mock_firebase_auth, client_with_mocks, valid_register_payload):
        """Test Firebase user is deleted when MongoDB creation fails."""
        client, mock_user_repo = client_with_mocks

        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = None

        # Firebase succeeds
        mock_firebase_user = MagicMock()
        mock_firebase_user.uid = "firebase_uid_123"
        mock_firebase_auth.create_user.return_value = mock_firebase_user

        # MongoDB fails
        mock_user_repo.create_user.side_effect = Exception("MongoDB error")

        response = client.post("/v1/auth/register", json=valid_register_payload)

        assert response.status_code == 500  # ERROR_CREATING_USER
        assert response.json()["error_code_name"] == ErrorCodes.ERROR_CREATING_USER.error_code_name

        # Verify rollback was attempted via repository → firebase_admin.auth
        mock_firebase_auth.delete_user.assert_called_once_with("firebase_uid_123")

    @patch('app.repository.firebase_auth_repository.auth')
    def test_register_validation_error(self, mock_firebase_auth, client_with_mocks):
        """Test registration fails with invalid payload."""
        client, _ = client_with_mocks

        invalid_payload = {
            "email": "not-an-email",
            "password": "123"  # Missing required fields
        }

        response = client.post("/v1/auth/register", json=invalid_payload)

        assert response.status_code == 422  # Validation error
        
        # Firebase should not be called for validation errors
        mock_firebase_auth.create_user.assert_not_called()
