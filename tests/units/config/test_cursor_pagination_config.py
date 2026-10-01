"""Tests for the dedicated cursor-pagination signing configuration."""

import importlib
import sys

import pytest

import app.config.cursor_pagination_config as cursor_pagination_config


def test_cursor_pagination_config_requires_its_dedicated_hmac_secret(monkeypatch: pytest.MonkeyPatch):
    original_module = cursor_pagination_config
    monkeypatch.delenv("CURSOR_PAGINATION_HMAC_SECRET")
    sys.modules.pop("app.config.cursor_pagination_config", None)

    try:
        with pytest.raises(ValueError, match="CURSOR_PAGINATION_HMAC_SECRET environment variable is not set"):
            importlib.import_module("app.config.cursor_pagination_config")
    finally:
        sys.modules["app.config.cursor_pagination_config"] = original_module
