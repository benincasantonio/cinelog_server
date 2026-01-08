import pytest
from unittest.mock import patch, Mock
from app.utils.access_token_utils import get_user_id_from_token


class TestGetUserIdFromToken:
    """Test cases for the get_user_id_from_token utility function."""

    def test_get_user_id_no_token(self):
        """Test that get_user_id_from_token raises ValueError for empty token."""
        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token(None)
        assert "No token provided" in str(exc_info.value)

    def test_get_user_id_empty_token(self):
        """Test that get_user_id_from_token raises ValueError for empty string token."""
        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("")
        assert "No token provided" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    @patch('app.repository.user_repository.UserRepository.find_user_by_firebase_uid')
    def test_get_user_id_success(self, mock_find_user, mock_verify_token):
        """Test successful user ID extraction from token."""
        mock_verify_token.return_value = {"uid": "firebase_uid_123"}
        
        mock_user = Mock()
        mock_user.id = Mock()
        mock_user.id.__str__ = Mock(return_value="user123")
        mock_find_user.return_value = mock_user

        result = get_user_id_from_token("Bearer valid_token")

        assert result == "user123"
        mock_verify_token.assert_called_once_with("valid_token", check_revoked=True)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    @patch('app.repository.user_repository.UserRepository.find_user_by_firebase_uid')
    def test_get_user_id_user_not_found(self, mock_find_user, mock_verify_token):
        """Test get_user_id_from_token when user is not found in DB."""
        mock_verify_token.return_value = {"uid": "firebase_uid_123"}
        mock_find_user.return_value = None

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("valid_token")
        assert "User not found" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    def test_get_user_id_no_uid_in_token(self, mock_verify_token):
        """Test get_user_id_from_token when token has no UID."""
        mock_verify_token.return_value = {}  # No uid

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("valid_token")
        assert "Token does not contain Firebase UID" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    def test_get_user_id_invalid_token(self, mock_verify_token):
        """Test get_user_id_from_token with invalid token."""
        from firebase_admin import auth
        mock_verify_token.side_effect = auth.InvalidIdTokenError("Invalid token")

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("invalid_token")
        assert "Invalid token" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    def test_get_user_id_expired_token(self, mock_verify_token):
        """Test get_user_id_from_token with expired token."""
        from firebase_admin import auth
        mock_verify_token.side_effect = auth.ExpiredIdTokenError("Token expired", None)

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("expired_token")
        assert "Token has expired" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    def test_get_user_id_revoked_token(self, mock_verify_token):
        """Test get_user_id_from_token with revoked token."""
        from firebase_admin import auth
        mock_verify_token.side_effect = auth.RevokedIdTokenError("Token revoked")

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("revoked_token")
        assert "Token has been revoked" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    def test_get_user_id_disabled_user(self, mock_verify_token):
        """Test get_user_id_from_token when user is disabled."""
        from firebase_admin import auth
        mock_verify_token.side_effect = auth.UserDisabledError("User disabled")

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("valid_token")
        assert "User account is disabled" in str(exc_info.value)

    @patch('app.repository.firebase_auth_repository.FirebaseAuthRepository.verify_id_token')
    def test_get_user_id_general_exception(self, mock_verify_token):
        """Test get_user_id_from_token with general exception."""
        mock_verify_token.side_effect = Exception("Some error")

        with pytest.raises(ValueError) as exc_info:
            get_user_id_from_token("valid_token")
        assert "Token validation failed" in str(exc_info.value)
