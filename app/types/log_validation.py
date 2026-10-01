"""
Log-domain validation functions and Annotated types.

Provides reusable validators for log-related fields such as the
``watched_where`` enum. Used by ``log_schemas``.

Types:
    WatchedWhereStr — required watched_where field (must be one of
                      the allowed choices)
"""

from typing import Annotated

from pydantic import AfterValidator

WATCHED_WHERE_CHOICES = ["cinema", "streaming", "homeVideo", "tv", "other"]


def validate_watched_where(v: str) -> str:
    if v not in WATCHED_WHERE_CHOICES:
        raise ValueError(f"watched_where must be one of {WATCHED_WHERE_CHOICES}")
    return v


WatchedWhereStr = Annotated[str, AfterValidator(validate_watched_where)]
