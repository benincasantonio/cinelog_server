"""Private validation and normalization for TMDB wire values.

TMDBReleaseDate accepts a date-only ISO value or an unknown (empty/null) date.
TMDBVoteAverage accepts finite 0–10 scores, converting numeric strings.
"""

from datetime import date
from typing import Annotated

from pydantic import BeforeValidator, Field


def validate_release_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if type(value) is date:
        return value
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
        return date.fromisoformat(value)
    raise ValueError("Expected a date in YYYY-MM-DD format")


TMDBReleaseDate = Annotated[date | None, BeforeValidator(validate_release_date)]


def parse_vote_average(value: object) -> object:
    return float(value) if isinstance(value, str) else value


TMDBVoteAverage = Annotated[
    float,
    Field(strict=True, ge=0, le=10, allow_inf_nan=False),
    BeforeValidator(parse_vote_average),
]
