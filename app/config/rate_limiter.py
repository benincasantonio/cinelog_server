"""
Rate limiter instance for the Cinelog API.

This module is intentionally kept separate from ``app/__init__.py`` to avoid
circular imports: controllers need to import the limiter at module load time,
but ``app/__init__.py`` also imports the controllers.

Import from here in controllers::

    from app.config.rate_limiter import limiter
"""

from slowapi import Limiter

from app.config.redis import get_redis_config
from app.utils.rate_limit_utils import get_rate_limit_key

_redis_config = get_redis_config()

limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=_redis_config["url"],
    headers_enabled=True,
    retry_after="delta-seconds",
)
