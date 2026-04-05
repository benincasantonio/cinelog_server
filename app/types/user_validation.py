"""
User-domain validation functions and Annotated types.

Provides reusable validators for user-related fields such as names,
handles, biographies, and profile visibility. Used by ``auth_schemas``
and ``user_schemas``.

Types:
    NameStr              — required name field (1–50 chars, validated characters)
    HandleStr            — required handle field (3–20 chars, alphanumeric + underscore)
    BioStr               — optional bio field (None or up to 500 chars, HTML stripped)
    ProfileVisibilityStr — required profile visibility ("public", "friends_only", "private")
"""

from typing import Annotated, Optional

from pydantic import AfterValidator, StringConstraints

from app.utils.sanitize_utils import HANDLE_PATTERN, NAME_PATTERN, strip_html_tags

PROFILE_VISIBILITY_CHOICES = ("public", "friends_only", "private")


def validate_name(v: str) -> str:
    v = v.strip()
    if not NAME_PATTERN.match(v):
        raise ValueError("Name contains invalid characters")
    return v


def validate_handle(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Handle must not be empty or whitespace")
    if v[0].isdigit():
        raise ValueError("Handle must not start with a number")
    if not HANDLE_PATTERN.match(v):
        raise ValueError(
            "Handle must contain only alphanumeric characters or underscores"
        )
    return v


def sanitize_bio(v: str) -> str:
    return strip_html_tags(v)


def validate_profile_visibility(v: str) -> str:
    v = v.strip().lower()
    if v not in PROFILE_VISIBILITY_CHOICES:
        raise ValueError(
            f"Profile visibility must be one of {PROFILE_VISIBILITY_CHOICES}"
        )
    return v


NameStr = Annotated[
    str, AfterValidator(validate_name), StringConstraints(min_length=1, max_length=50)
]

HandleStr = Annotated[
    str,
    AfterValidator(validate_handle),
    StringConstraints(min_length=3, max_length=20),
]

BioStr = Optional[
    Annotated[str, AfterValidator(sanitize_bio), StringConstraints(max_length=500)]
]

ProfileVisibilityStr = Annotated[
    str,
    AfterValidator(validate_profile_visibility),
]
