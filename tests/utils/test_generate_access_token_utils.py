import os
import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch

from app.utils.generate_access_token import generate_access_token


class TestGenerateAccessToken:
    """Test cases for the generate_access_token utility function."""

    @patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret_key"})
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
          # Verify the expiration time (should be around 1 hour from now)
        current_time = datetime.utcnow().timestamp()
        expected_exp_time = (datetime.utcnow() + timedelta(hours=1)).timestamp()
        
        # Allow for a reasonable time difference due to execution time
        assert abs(decoded_token["exp"] - expected_exp_time) < 10  # Within 10 seconds
        
    @patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret_key"})
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
          # Calculate expected expiration (1 hour from now)
        current_time = datetime.utcnow().timestamp()
        # The token should expire in approximately 1 hour
        assert decoded_token["exp"] > current_time
        
        # Add a buffer of 2 hours to account for any time drift and test execution time
        assert decoded_token["exp"] <= current_time + 7200  # 2 hours in seconds