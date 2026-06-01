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


def test_user_create_request_normalizes_profile_visibility():
    request = UserCreateRequest(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        handle="johndoe",
        date_of_birth=date(1990, 1, 1),
        profile_visibility=" PUBLIC ",
    )

    assert request.profile_visibility == "public"
