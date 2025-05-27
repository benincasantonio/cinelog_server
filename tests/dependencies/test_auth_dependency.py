import pytest
from unittest.mock import Mock, patch
from app.dependencies.auth_dependency import auth_dependency
from fastapi import HTTPException

class TestAuthDependency:
    """Test cases for the AuthDependency class."""

    def test_when_token_is_valid(self):
        """Test that auth_dependency allows access when a valid token is provided."""

        mock_request = Mock()
        mock_request.headers = {"Authorization": "valid_token"}

        with patch('app.dependencies.auth_dependency.is_valid_access_token', return_value=True):
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
        mock_request.headers = {"Authorization": "invalid_token"}

        with patch('app.dependencies.auth_dependency.is_valid_access_token', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                auth_dependency(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Unauthorized"

