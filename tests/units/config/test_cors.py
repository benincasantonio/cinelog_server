import os
from unittest.mock import patch
from app.config.cors import get_cors_origins, get_cors_config


def test_get_cors_origins_from_env():
    with patch.dict(
        os.environ, {"CORS_ORIGINS": "https://example.com , https://test.com"}
    ):
        origins = get_cors_origins()
        assert origins == ["https://example.com", "https://test.com"]


def test_get_cors_origins_from_env_filters_empty_values():
    with patch.dict(
        os.environ, {"CORS_ORIGINS": "https://example.com,, https://test.com, ,"}
    ):
        origins = get_cors_origins()
        assert origins == ["https://example.com", "https://test.com"]


def test_get_cors_origins_dev_defaults():
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
        origins = get_cors_origins()
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins


def test_get_cors_origins_production_empty():
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
        origins = get_cors_origins()
        assert origins == []


def test_get_cors_config_credentials():
    with patch.dict(os.environ, {"CORS_ALLOW_CREDENTIALS": "false"}):
        config = get_cors_config()
        assert config["allow_credentials"] is False

    with patch.dict(os.environ, {"CORS_ALLOW_CREDENTIALS": "true"}):
        config = get_cors_config()
        assert config["allow_credentials"] is True


def test_get_cors_config_defaults():
    config = get_cors_config()
    assert "allow_origins" in config
    assert config["allow_methods"] == [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "OPTIONS",
    ]
    assert config["allow_headers"] == ["Content-Type", "Accept", "X-CSRF-Token"]
