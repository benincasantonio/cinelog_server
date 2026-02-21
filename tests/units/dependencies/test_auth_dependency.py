import pytest
from unittest.mock import Mock, patch
from app.dependencies.auth_dependency import auth_dependency
from fastapi import HTTPException
from jwt import ExpiredSignatureError, InvalidTokenError

class TestAuthDependency:
    """Test cases for the AuthDependency class."""

    def test_when_cookie_is_valid(self):
        """Test that auth_dependency allows access when a valid cookie is provided."""
        mock_request = Mock()
        mock_request.cookies = {"__Host-access_token": "valid_token"}
        mock_request.headers = {}

        with patch('app.dependencies.auth_dependency.TokenService.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": "user123", "type": "access"}
            
            result = auth_dependency(mock_request)
            
            assert result == "user123"
            mock_decode.assert_called_once_with("valid_token")

    def test_when_cookie_is_missing(self):
        """Test that auth_dependency raises an HTTPException when no cookie is provided."""
        mock_request = Mock()
        mock_request.cookies = {}
        mock_request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            auth_dependency(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Unauthorized"

    def test_when_token_is_invalid(self):
        """Test function raises HTTPException when token is invalid."""
        mock_request = Mock()
        mock_request.cookies = {"__Host-access_token": "invalid_token"}
        mock_request.headers = {}

        with patch('app.dependencies.auth_dependency.TokenService.decode_token', side_effect=InvalidTokenError):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Unauthorized"

    def test_when_token_is_expired(self):
        """Test function raises HTTPException when token is expired."""
        mock_request = Mock()
        mock_request.cookies = {"__Host-access_token": "expired_token"}
        mock_request.headers = {}

        with patch('app.dependencies.auth_dependency.TokenService.decode_token', side_effect=ExpiredSignatureError):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Unauthorized"

    def test_when_token_type_is_invalid(self):
        """Test function raises HTTPException when token type is not 'access'."""
        mock_request = Mock()
        mock_request.cookies = {"__Host-access_token": "refresh_token"}
        mock_request.headers = {}

        with patch('app.dependencies.auth_dependency.TokenService.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": "user123", "type": "refresh"}
            
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid token type"

    def test_when_token_payload_missing_sub(self):
        """Test function raises HTTPException when token payload is missing 'sub'."""
        mock_request = Mock()
        mock_request.cookies = {"__Host-access_token": "valid_token"}
        mock_request.headers = {}

        with patch('app.dependencies.auth_dependency.TokenService.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access"} # Missing sub
            
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid token payload"
