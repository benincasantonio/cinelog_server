import os
import jwt
from datetime import datetime, timedelta, UTC
from unittest.mock import patch
from freezegun import freeze_time
from app.utils.generate_access_token import generate_access_token


class TestGenerateAccessToken:
    """Test cases for the generate_access_token utility function."""




    @patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret_key"})
    @freeze_time("2023-10-01")
    def test_generate_access_token_creates_valid_token(self):
        """Test that generate_access_token creates a valid JWT token with correct payload."""
        # Arrange
        test_user_id = "test_user_123"
        
        # Act
        token = generate_access_token(test_user_id)
        
        # Assert
        # Verify that a token is returned
        assert token is not None
        
        # Decode the token to verify its contents
        decoded_token = jwt.decode(
            token, 
            os.environ.get("JWT_SECRET_KEY"), 
            algorithms=["HS256"]
        )
        
        # Verify the user_id is in the token
        assert decoded_token["sub"] == test_user_id
        # Verify the expiration time
        assert "exp" in decoded_token
        # Verify the expiration time is set to 1 hour from now
        expected_expiration = datetime.utcnow() + timedelta(hours=1)
        assert decoded_token["exp"] == int(expected_expiration.timestamp())
        
    @patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret_key"})
    @freeze_time("2023-10-01")
    def test_token_expiration(self):
        """Test that the token expires after the set time."""
        # Arrange
        test_user_id = "test_user_456"
        
        # Act
        token = generate_access_token(test_user_id)
        decoded_token = jwt.decode(
            token, 
            os.environ.get("JWT_SECRET_KEY"), 
            algorithms=["HS256"]
        )
        
        # Assert
        # Verify the token has an expiration time
        assert "exp" in decoded_token
        # Verify the expiration time is set to 1 hour from now
        expected_expiration = datetime.now(UTC) + timedelta(hours=1)
        assert decoded_token["exp"] == int(expected_expiration.timestamp())
