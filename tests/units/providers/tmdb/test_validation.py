from datetime import UTC, date, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.providers.tmdb.validation import TMDBReleaseDate, TMDBVoteAverage


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("", None), ("2024-02-29", date(2024, 2, 29)), (date(2024, 1, 1), date(2024, 1, 1))],
)
def test_release_date_preserves_date_only_and_unknown(value, expected):
    assert TypeAdapter(TMDBReleaseDate).validate_python(value) == expected


@pytest.mark.parametrize("value", ["2024-02-30", "20240101", "2024-01-01T00:00:00Z", 1704067200, datetime.now(UTC)])
def test_release_date_rejects_malformed_or_timestamp_values(value):
    with pytest.raises(ValidationError):
        TypeAdapter(TMDBReleaseDate).validate_python(value)


@pytest.mark.parametrize(
    ("value", "expected"), [(0, 0.0), (10, 10.0), (8.4, 8.4), ("8.4", 8.4), ("0", 0.0), ("10", 10.0)]
)
def test_vote_average_parses_numbers_and_numeric_strings(value, expected):
    result = TypeAdapter(TMDBVoteAverage).validate_python(value)
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.parametrize(
    "value",
    [None, True, False, "abc", "", [], {}, -0.1, 10.1, "10.1", "NaN", "Infinity", float("nan"), float("inf")],
)
def test_vote_average_rejects_malformed_nonfinite_and_out_of_range_values(value):
    with pytest.raises(ValidationError):
        TypeAdapter(TMDBVoteAverage).validate_python(value)
