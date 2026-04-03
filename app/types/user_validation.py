"""
User-domain validation functions and Annotated types.

Provides reusable validators for user-related fields such as names,
handles, and biographies. Used by ``auth_schemas`` and ``user_schemas``.

Types:
    NameStr             — required name field (1–50 chars, validated characters)
    OptionalNameStr     — optional name field (None or 1–50 chars)
    HandleStr           — required handle field (3–20 chars, alphanumeric + underscore)
    OptionalHandleStr   — optional handle field (None or 3–20 chars)
    BioStr              — optional bio field (None or up to 500 chars, HTML stripped)
    ProfileVisibilityStr — required profile visibility field (public, friends_only, private)
"""

from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, StringConstraints

from app.utils.sanitize_utils import HANDLE_PATTERN, NAME_PATTERN, strip_html_tags

PROFILE_VISIBILITY_VALUES = ("public", "friends_only", "private")


def validate_profile_visibility(v: str) -> str:
    if v not in PROFILE_VISIBILITY_VALUES:
        raise ValueError(
            f"Profile visibility must be one of: {', '.join(PROFILE_VISIBILITY_VALUES)}"
        )
    return v


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


NameStr = Annotated[
    str, AfterValidator(validate_name), StringConstraints(min_length=1, max_length=50)
]

OptionalNameStr = Optional[
    Annotated[
        str,
        AfterValidator(validate_name),
        StringConstraints(min_length=1, max_length=50),
    ]
]

HandleStr = Annotated[
    str,
    AfterValidator(validate_handle),
    StringConstraints(min_length=3, max_length=20),
]

OptionalHandleStr = Optional[
    Annotated[
        str,
        AfterValidator(validate_handle),
        StringConstraints(min_length=3, max_length=20),
    ]
]

BioStr = Optional[
    Annotated[str, AfterValidator(sanitize_bio), StringConstraints(max_length=500)]
]

ProfileVisibilityStr = Literal["public", "friends_only", "private"]
