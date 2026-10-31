"""Configuration for signed, stateless search-result movie references."""

import os

MOVIE_REF_VERSION = 1

_movie_ref_hmac_secret = os.getenv("MOVIE_REF_HMAC_SECRET")
if not _movie_ref_hmac_secret:
    raise ValueError("MOVIE_REF_HMAC_SECRET environment variable is not set. Application cannot start.")

MOVIE_REF_HMAC_SECRET: str = _movie_ref_hmac_secret
