from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.user_schemas import UserCreateRequest


def test_user_create_request_rejects_invalid_profile_visibility():
    with pytest.raises(ValidationError):
        UserCreateRequest(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="hidden",
        )


def test_user_create_request_normalizes_followers_only_profile_visibility():
    request = UserCreateRequest(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        handle="johndoe",
        date_of_birth=date(1990, 1, 1),
        profile_visibility=" FOLLOWERS_ONLY ",
    )

    assert request.profile_visibility == "followers_only"


def test_user_create_request_rejects_friends_only_profile_visibility():
    with pytest.raises(ValidationError):
        UserCreateRequest(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="friends_only",
        )
