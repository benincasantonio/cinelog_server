import os
from typing import TypedDict, List

class CORSConfig(TypedDict):
    allow_origins: List[str]
    allow_credentials: bool
    allow_methods: List[str]
    allow_headers: List[str]

def get_cors_origins() -> List[str]:
    """
    Get allowed CORS origins based on environment and CORS_ORIGINS variable.
    """
    cors_origins = os.getenv("CORS_ORIGINS")
    if cors_origins:
        # Split by comma, trim whitespace, and filter out empty strings
        return [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "development":
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

    return []

def get_cors_config() -> CORSConfig:
    """
    Returns the configuration dictionary for CORSMiddleware.
    """
    allow_credentials_str = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower()
    allow_credentials = allow_credentials_str == "true"

    return {
        "allow_origins": get_cors_origins(),
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept", "X-CSRF-Token"],
    }
