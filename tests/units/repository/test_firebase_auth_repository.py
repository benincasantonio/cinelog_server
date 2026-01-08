"""
Unit tests for FirebaseAuthRepository.
Tests all Firebase Auth operations with mocked Firebase SDK.
"""

import pytest
from unittest.mock import Mock, patch
from firebase_admin import auth

from app.repository.firebase_auth_repository import FirebaseAuthRepository


class TestFirebaseAuthRepository:
    """Test cases for FirebaseAuthRepository."""

    # ==================== verify_id_token tests ====================

    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_verify_id_token_firebase_not_initialized(self, mock_is_initialized):
        """Test verify_id_token raises ValueError when Firebase is not initialized."""
        mock_is_initialized.return_value = False

        with pytest.raises(ValueError) as exc_info:
            FirebaseAuthRepository.verify_id_token("some_token")

        assert "Firebase Admin SDK is not initialized" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.auth.verify_id_token')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_verify_id_token_success(self, mock_is_initialized, mock_verify):
        """Test verify_id_token returns decoded token when valid."""
        mock_is_initialized.return_value = True
        expected_claims = {"uid": "test_uid", "email": "test@example.com"}
        mock_verify.return_value = expected_claims

        result = FirebaseAuthRepository.verify_id_token("valid_token")

        assert result == expected_claims
        mock_verify.assert_called_once_with("valid_token", check_revoked=False)

    @patch('app.repository.firebase_auth_repository.auth.verify_id_token')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_verify_id_token_with_check_revoked(self, mock_is_initialized, mock_verify):
        """Test verify_id_token passes check_revoked parameter."""
        mock_is_initialized.return_value = True
        mock_verify.return_value = {"uid": "test_uid"}

        FirebaseAuthRepository.verify_id_token("valid_token", check_revoked=True)

        mock_verify.assert_called_once_with("valid_token", check_revoked=True)

    # ==================== get_user tests ====================

    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_get_user_firebase_not_initialized(self, mock_is_initialized):
        """Test get_user raises ValueError when Firebase is not initialized."""
        mock_is_initialized.return_value = False

        with pytest.raises(ValueError) as exc_info:
            FirebaseAuthRepository.get_user("some_uid")

        assert "Firebase Admin SDK is not initialized" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.auth.get_user')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_get_user_success(self, mock_is_initialized, mock_get_user):
        """Test get_user returns user record when found."""
        mock_is_initialized.return_value = True
        mock_user = Mock()
        mock_user.uid = "test_uid"
        mock_user.email = "test@example.com"
        mock_get_user.return_value = mock_user

        result = FirebaseAuthRepository.get_user("test_uid")

        assert result.uid == "test_uid"
        assert result.email == "test@example.com"
        mock_get_user.assert_called_once_with("test_uid")

    # ==================== get_user_by_email tests ====================

    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_get_user_by_email_firebase_not_initialized(self, mock_is_initialized):
        """Test get_user_by_email raises ValueError when Firebase is not initialized."""
        mock_is_initialized.return_value = False

        with pytest.raises(ValueError) as exc_info:
            FirebaseAuthRepository.get_user_by_email("test@example.com")

        assert "Firebase Admin SDK is not initialized" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.auth.get_user_by_email')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_get_user_by_email_success(self, mock_is_initialized, mock_get_user_by_email):
        """Test get_user_by_email returns user record when found."""
        mock_is_initialized.return_value = True
        mock_user = Mock()
        mock_user.uid = "test_uid"
        mock_user.email = "test@example.com"
        mock_get_user_by_email.return_value = mock_user

        result = FirebaseAuthRepository.get_user_by_email("test@example.com")

        assert result.uid == "test_uid"
        assert result.email == "test@example.com"
        mock_get_user_by_email.assert_called_once_with("test@example.com")

    # ==================== create_user tests ====================

    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_create_user_firebase_not_initialized(self, mock_is_initialized):
        """Test create_user raises ValueError when Firebase is not initialized."""
        mock_is_initialized.return_value = False

        with pytest.raises(ValueError) as exc_info:
            FirebaseAuthRepository.create_user(email="test@example.com", password="password123")

        assert "Firebase Admin SDK is not initialized" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.auth.create_user')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_create_user_success_minimal(self, mock_is_initialized, mock_create_user):
        """Test create_user with minimal parameters."""
        mock_is_initialized.return_value = True
        mock_user = Mock()
        mock_user.uid = "new_uid"
        mock_create_user.return_value = mock_user

        result = FirebaseAuthRepository.create_user(
            email="test@example.com",
            password="password123"
        )

        assert result.uid == "new_uid"
        mock_create_user.assert_called_once_with(
            email="test@example.com",
            password="password123",
            email_verified=False,
            disabled=False
        )

    @patch('app.repository.firebase_auth_repository.auth.create_user')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_create_user_success_all_params(self, mock_is_initialized, mock_create_user):
        """Test create_user with all parameters."""
        mock_is_initialized.return_value = True
        mock_user = Mock()
        mock_user.uid = "custom_uid"
        mock_create_user.return_value = mock_user

        result = FirebaseAuthRepository.create_user(
            email="test@example.com",
            password="password123",
            uid="custom_uid",
            display_name="Test User",
            phone_number="+1234567890",
            email_verified=True,
            disabled=False,
            photo_url="https://example.com/photo.jpg"
        )

        assert result.uid == "custom_uid"
        mock_create_user.assert_called_once_with(
            email="test@example.com",
            password="password123",
            uid="custom_uid",
            display_name="Test User",
            phone_number="+1234567890",
            photo_url="https://example.com/photo.jpg",
            email_verified=True,
            disabled=False
        )

    # ==================== update_user tests ====================

    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_update_user_firebase_not_initialized(self, mock_is_initialized):
        """Test update_user raises ValueError when Firebase is not initialized."""
        mock_is_initialized.return_value = False

        with pytest.raises(ValueError) as exc_info:
            FirebaseAuthRepository.update_user("some_uid", email="new@example.com")

        assert "Firebase Admin SDK is not initialized" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.auth.update_user')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_update_user_success_single_field(self, mock_is_initialized, mock_update_user):
        """Test update_user with single field update."""
        mock_is_initialized.return_value = True
        mock_user = Mock()
        mock_user.uid = "test_uid"
        mock_update_user.return_value = mock_user

        result = FirebaseAuthRepository.update_user("test_uid", email="new@example.com")

        assert result.uid == "test_uid"
        mock_update_user.assert_called_once_with("test_uid", email="new@example.com")

    @patch('app.repository.firebase_auth_repository.auth.update_user')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_update_user_success_all_fields(self, mock_is_initialized, mock_update_user):
        """Test update_user with all fields."""
        mock_is_initialized.return_value = True
        mock_user = Mock()
        mock_update_user.return_value = mock_user

        FirebaseAuthRepository.update_user(
            "test_uid",
            email="new@example.com",
            password="newpassword123",
            display_name="New Name",
            phone_number="+0987654321",
            email_verified=True,
            disabled=True,
            photo_url="https://new.example.com/photo.jpg"
        )

        mock_update_user.assert_called_once_with(
            "test_uid",
            email="new@example.com",
            password="newpassword123",
            display_name="New Name",
            phone_number="+0987654321",
            email_verified=True,
            disabled=True,
            photo_url="https://new.example.com/photo.jpg"
        )

    # ==================== delete_user tests ====================

    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_delete_user_firebase_not_initialized(self, mock_is_initialized):
        """Test delete_user raises ValueError when Firebase is not initialized."""
        mock_is_initialized.return_value = False

        with pytest.raises(ValueError) as exc_info:
            FirebaseAuthRepository.delete_user("some_uid")

        assert "Firebase Admin SDK is not initialized" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.auth.delete_user')
    @patch('app.repository.firebase_auth_repository.is_firebase_initialized')
    def test_delete_user_success(self, mock_is_initialized, mock_delete_user):
        """Test delete_user successfully deletes user."""
        mock_is_initialized.return_value = True
        mock_delete_user.return_value = None

        # Should not raise any exception
        FirebaseAuthRepository.delete_user("test_uid")

        mock_delete_user.assert_called_once_with("test_uid")
