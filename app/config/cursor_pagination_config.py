"""Shared configuration for signed cursor pagination."""

import os

CURSOR_PAGINATION_VERSION = 1

_cursor_pagination_hmac_secret = os.getenv("CURSOR_PAGINATION_HMAC_SECRET")
if not _cursor_pagination_hmac_secret:
    raise ValueError("CURSOR_PAGINATION_HMAC_SECRET environment variable is not set. Application cannot start.")

CURSOR_PAGINATION_HMAC_SECRET: str = _cursor_pagination_hmac_secret
