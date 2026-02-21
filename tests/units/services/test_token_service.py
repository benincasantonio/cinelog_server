import pytest
from datetime import timedelta
from app.services.token_service import TokenService
import jwt

class TestTokenService:
    def test_create_access_token(self):
        data = {"sub": "user_123"}
        token = TokenService.create_access_token(data)
        
        decoded = TokenService.decode_token(token)
        assert decoded["sub"] == "user_123"
        assert decoded["type"] == "access"
        assert "exp" in decoded

    def test_create_refresh_token(self):
        data = {"sub": "user_123"}
        token = TokenService.create_refresh_token(data)
        
        decoded = TokenService.decode_token(token)
        assert decoded["sub"] == "user_123"
        assert decoded["type"] == "refresh"
        assert "exp" in decoded

    def test_token_expiration(self):
        data = {"sub": "user_123"}
        # Create token that expires immediately
        token = TokenService.create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        with pytest.raises(jwt.ExpiredSignatureError):
            TokenService.decode_token(token)
