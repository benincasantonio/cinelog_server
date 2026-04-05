import pytest
from pydantic import BaseModel, ValidationError

from app.types import ProfileVisibilityStr


class ProfileVisibilityModel(BaseModel):
    visibility: ProfileVisibilityStr


class TestProfileVisibilityValidation:
    def test_valid_public(self):
        model = ProfileVisibilityModel(visibility="public")
        assert model.visibility == "public"

    def test_valid_private(self):
        model = ProfileVisibilityModel(visibility="private")
        assert model.visibility == "private"

    def test_valid_friends_only(self):
        model = ProfileVisibilityModel(visibility="friends_only")
        assert model.visibility == "friends_only"

    def test_valid_uppercase_normalized(self):
        model = ProfileVisibilityModel(visibility="PUBLIC")
        assert model.visibility == "public"

    def test_valid_with_whitespace(self):
        model = ProfileVisibilityModel(visibility="  public  ")
        assert model.visibility == "public"

    def test_invalid_value(self):
        with pytest.raises(ValidationError):
            ProfileVisibilityModel(visibility="hidden")

    def test_invalid_empty(self):
        with pytest.raises(ValidationError):
            ProfileVisibilityModel(visibility="")
