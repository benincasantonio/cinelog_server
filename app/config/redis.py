import os
from typing import TypedDict


class RedisConfig(TypedDict):
    enabled: bool
    url: str
    default_ttl: int


def get_redis_config() -> RedisConfig:
    """
    Returns Redis configuration from environment variables.
    """
    enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    default_ttl = int(os.getenv("REDIS_DEFAULT_TTL", "300"))

    return {
        "enabled": enabled,
        "url": url,
        "default_ttl": default_ttl,
    }
