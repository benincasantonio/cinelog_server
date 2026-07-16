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

    def test_valid_followers_only(self):
        model = ProfileVisibilityModel(visibility="followers_only")
        assert model.visibility == "followers_only"

    def test_followers_only_is_normalized(self):
        model = ProfileVisibilityModel(visibility=" FOLLOWERS_ONLY ")
        assert model.visibility == "followers_only"

    def test_friends_only_is_rejected(self):
        with pytest.raises(ValidationError):
            ProfileVisibilityModel(visibility="friends_only")

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
