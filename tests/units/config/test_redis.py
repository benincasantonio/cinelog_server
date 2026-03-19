import os
from unittest.mock import patch

from app.config.redis import get_redis_config


def test_get_redis_config_defaults():
    with patch.dict(os.environ, {}, clear=True):
        config = get_redis_config()
        assert config["enabled"] is False
        assert config["url"] == "redis://localhost:6379/0"
        assert config["default_ttl"] == 300


def test_get_redis_config_enabled_true():
    with patch.dict(os.environ, {"REDIS_ENABLED": "true"}):
        config = get_redis_config()
        assert config["enabled"] is True


def test_get_redis_config_enabled_true_uppercase():
    with patch.dict(os.environ, {"REDIS_ENABLED": "TRUE"}):
        config = get_redis_config()
        assert config["enabled"] is True


def test_get_redis_config_enabled_false():
    with patch.dict(os.environ, {"REDIS_ENABLED": "false"}):
        config = get_redis_config()
        assert config["enabled"] is False


def test_get_redis_config_custom_url():
    with patch.dict(os.environ, {"REDIS_URL": "redis://myhost:6380/1"}):
        config = get_redis_config()
        assert config["url"] == "redis://myhost:6380/1"


def test_get_redis_config_custom_ttl():
    with patch.dict(os.environ, {"REDIS_DEFAULT_TTL": "600"}):
        config = get_redis_config()
        assert config["default_ttl"] == 600
