"""Configuration for the registration email-verification flow.

Exposes the cache TTL, attempt limit, cache-key prefix, and the HMAC secret
used to hash verification codes and keys. The HMAC secret is read at import
time and the application fails fast if it is not configured.
"""

import os

REGISTRATION_VERIFICATION_TTL_SECONDS = 15 * 60
REGISTRATION_VERIFICATION_MAX_ATTEMPTS = 5
REGISTRATION_VERIFICATION_CACHE_PREFIX = "auth:register-verification:"

_hmac_secret = os.getenv("REGISTRATION_VERIFICATION_HMAC_SECRET")
if not _hmac_secret:
    raise ValueError("REGISTRATION_VERIFICATION_HMAC_SECRET environment variable is not set. Application cannot start.")

REGISTRATION_VERIFICATION_HMAC_SECRET: str = _hmac_secret
