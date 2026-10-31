"""Tests for the dedicated movieRef signing configuration."""

import importlib
import sys

import pytest

import app.config.movie_ref_config as movie_ref_config


def test_movie_ref_config_requires_its_dedicated_hmac_secret(monkeypatch: pytest.MonkeyPatch):
    original_module = movie_ref_config
    monkeypatch.delenv("MOVIE_REF_HMAC_SECRET")
    sys.modules.pop("app.config.movie_ref_config", None)

    try:
        with pytest.raises(ValueError, match="MOVIE_REF_HMAC_SECRET environment variable is not set"):
            importlib.import_module("app.config.movie_ref_config")
    finally:
        sys.modules["app.config.movie_ref_config"] = original_module
