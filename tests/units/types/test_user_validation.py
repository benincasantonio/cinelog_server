import pytest
from pydantic import BaseModel, ValidationError

from app.types import LocaleStr, ProfileVisibilityStr


class ProfileVisibilityModel(BaseModel):
    visibility: ProfileVisibilityStr


class LocaleModel(BaseModel):
    locale: LocaleStr


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


class TestLocaleValidation:
    @pytest.mark.parametrize("locale", ["en-US", "fr-FR", "it-IT"])
    def test_supported_locale(self, locale):
        assert LocaleModel(locale=locale).locale == locale

    def test_normalizes_supported_locale(self):
        assert LocaleModel(locale="  IT-it ").locale == "it-IT"

    @pytest.mark.parametrize("locale", ["en-GB", "de-DE", "en", ""])
    def test_rejects_unsupported_locale(self, locale):
        with pytest.raises(ValidationError):
            LocaleModel(locale=locale)
