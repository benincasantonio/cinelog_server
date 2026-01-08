import pytest
from unittest.mock import Mock, patch
from app.dependencies.auth_dependency import auth_dependency
from fastapi import HTTPException
from firebase_admin import auth

class TestAuthDependency:
    """Test cases for the AuthDependency class."""

    def test_when_token_is_valid(self):
        """Test that auth_dependency allows access when a valid token is provided."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', return_value={"uid": "test_uid"}):
            result = auth_dependency(mock_request)
            assert result is True

    def test_when_header_is_missing(self):
        """Test that auth_dependency raises an HTTPException when no token is provided."""

        mock_request = Mock()
        mock_request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            auth_dependency(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Unauthorized"

    def test_when_token_is_invalid(self):
        """Test that auth_dependency raises an HTTPException when an invalid token is provided."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', side_effect=auth.InvalidIdTokenError("Invalid token")):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid token"

    def test_when_token_is_expired(self):
        """Test that auth_dependency raises an HTTPException when an expired token is provided."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer expired_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', side_effect=auth.ExpiredIdTokenError("Token expired", None)):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Token expired"

    def test_when_token_is_revoked(self):
        """Test that auth_dependency raises an HTTPException when a revoked token is provided."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer revoked_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', side_effect=auth.RevokedIdTokenError("Token revoked")):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Token revoked"

    def test_when_firebase_not_initialized(self):
        """Test that auth_dependency raises HTTPException when Firebase is not initialized."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', side_effect=ValueError("Firebase not initialized")):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Unauthorized"

    def test_when_user_is_disabled(self):
        """Test that auth_dependency raises HTTPException when user account is disabled."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', side_effect=auth.UserDisabledError("User disabled")):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "User account is disabled"

    def test_when_generic_exception_occurs(self):
        """Test that auth_dependency raises HTTPException on generic exception."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', side_effect=Exception("Some error")):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Unauthorized"

    def test_when_token_without_bearer_prefix(self):
        """Test that auth_dependency works with token without Bearer prefix."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "raw_token_without_bearer"}

        with patch('app.dependencies.auth_dependency.FirebaseAuthRepository.verify_id_token', return_value={"uid": "test_uid"}):
            result = auth_dependency(mock_request)
            assert result is True
