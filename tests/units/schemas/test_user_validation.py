"""
Unit tests for user type validators.
Tests ProfileVisibilityStr and validate_profile_visibility.
"""

import pytest
from pydantic import ValidationError
from datetime import date

from app.types.user_validation import (
    PROFILE_VISIBILITY_VALUES,
    ProfileVisibilityStr,
    validate_profile_visibility,
)
from app.schemas.auth_schemas import RegisterRequest
from app.schemas.user_schemas import UpdateProfileRequest


class TestValidateProfileVisibility:
    """Tests for validate_profile_visibility validator function."""

    def test_valid_public(self):
        """Test that 'public' is accepted."""
        assert validate_profile_visibility("public") == "public"

    def test_valid_friends_only(self):
        """Test that 'friends_only' is accepted."""
        assert validate_profile_visibility("friends_only") == "friends_only"

    def test_valid_private(self):
        """Test that 'private' is accepted."""
        assert validate_profile_visibility("private") == "private"

    def test_invalid_value_raises(self):
        """Test that an invalid value raises ValueError."""
        with pytest.raises(ValueError, match="Profile visibility must be one of"):
            validate_profile_visibility("everyone")

    def test_profile_visibility_values_constant(self):
        """Test that PROFILE_VISIBILITY_VALUES contains the expected values."""
        assert "public" in PROFILE_VISIBILITY_VALUES
        assert "friends_only" in PROFILE_VISIBILITY_VALUES
        assert "private" in PROFILE_VISIBILITY_VALUES
        assert len(PROFILE_VISIBILITY_VALUES) == 3


class TestRegisterRequestProfileVisibility:
    """Tests for profileVisibility field in RegisterRequest."""

    def _base_request(self, **kwargs):
        defaults = dict(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="securepass123",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="public",
        )
        defaults.update(kwargs)
        return defaults

    def test_register_with_public_visibility(self):
        """Test registration with public visibility."""
        req = RegisterRequest(**self._base_request(profile_visibility="public"))
        assert req.profile_visibility == "public"

    def test_register_with_friends_only_visibility(self):
        """Test registration with friends_only visibility."""
        req = RegisterRequest(**self._base_request(profile_visibility="friends_only"))
        assert req.profile_visibility == "friends_only"

    def test_register_with_private_visibility(self):
        """Test registration with private visibility."""
        req = RegisterRequest(**self._base_request(profile_visibility="private"))
        assert req.profile_visibility == "private"

    def test_register_missing_profile_visibility_raises(self):
        """Test that missing profileVisibility raises ValidationError."""
        data = self._base_request()
        del data["profile_visibility"]
        with pytest.raises(ValidationError):
            RegisterRequest(**data)

    def test_register_invalid_profile_visibility_raises(self):
        """Test that invalid profileVisibility raises ValidationError."""
        with pytest.raises(ValidationError):
            RegisterRequest(**self._base_request(profile_visibility="unknown"))


class TestUpdateProfileRequestProfileVisibility:
    """Tests for profileVisibility in UpdateProfileRequest."""

    def test_update_with_valid_visibility(self):
        """Test that profile visibility can be updated."""
        req = UpdateProfileRequest(profile_visibility="public")
        assert req.profile_visibility == "public"

    def test_update_with_no_visibility(self):
        """Test that profile visibility is optional in update."""
        req = UpdateProfileRequest(first_name="John")
        assert req.profile_visibility is None

    def test_update_with_invalid_visibility_raises(self):
        """Test that invalid visibility raises ValidationError."""
        with pytest.raises(ValidationError):
            UpdateProfileRequest(profile_visibility="everyone")
