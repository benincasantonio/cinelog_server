from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.user_schemas import UserCreateRequest, UserProfileResponse


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


def test_user_profile_response_serializes_follow_summary_in_camel_case():
    response = UserProfileResponse(
        first_name="Jane",
        last_name="Doe",
        handle="janedoe",
        profile_visibility="public",
        date_of_birth=date(1990, 1, 1),
        follower_count=12,
        following_count=8,
        is_following=True,
    )

    payload = response.model_dump(by_alias=True)

    assert payload["followerCount"] == 12
    assert payload["followingCount"] == 8
    assert payload["isFollowing"] is True
