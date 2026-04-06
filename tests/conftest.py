import os
import pytest
from unittest.mock import patch

# Set environment variables for testing before any app imports
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["RATE_LIMIT_HMAC_SECRET"] = "test-rate-limit-hmac-secret"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Ensure environment variables are set for all tests."""
    with patch.dict(
        os.environ,
        {
            "JWT_SECRET_KEY": "test-secret-key",
            "RATE_LIMIT_HMAC_SECRET": "test-rate-limit-hmac-secret",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "15",
            "REFRESH_TOKEN_EXPIRE_DAYS": "7",
        },
    ):
        yield
