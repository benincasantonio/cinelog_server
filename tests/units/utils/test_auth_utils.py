import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request
from app.utils.auth_utils import is_authenticated, ACCESS_TOKEN_COOKIE

def test_is_authenticated_no_token():
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = None
    
    result = is_authenticated(request)
    assert result is None
    request.cookies.get.assert_called_once_with(ACCESS_TOKEN_COOKIE)

@patch("app.utils.auth_utils.TokenService.decode_token")
def test_is_authenticated_valid_token(mock_decode):
    mock_decode.return_value = {"type": "access", "sub": "user_123"}
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "valid_token"
    
    result = is_authenticated(request)
    assert result == "user_123"
    mock_decode.assert_called_once_with("valid_token")

@patch("app.utils.auth_utils.TokenService.decode_token")
def test_is_authenticated_invalid_type(mock_decode):
    mock_decode.return_value = {"type": "refresh", "sub": "user_123"}
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "refresh_token"
    
    result = is_authenticated(request)
    assert result is None

@patch("app.utils.auth_utils.TokenService.decode_token")
def test_is_authenticated_decode_exception(mock_decode):
    mock_decode.side_effect = Exception("Invalid token")
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "bad_token"
    
    result = is_authenticated(request)
    assert result is None
