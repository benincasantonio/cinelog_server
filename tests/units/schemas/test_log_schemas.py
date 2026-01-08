"""
Unit tests for log schemas validators.
Tests all validator functions in log_schemas.py.
"""

import pytest
from datetime import date
from pydantic import ValidationError

from app.schemas.log_schemas import (
    LogCreateRequest,
    LogUpdateRequest,
    LogListRequest,
)


class TestLogCreateRequest:
    """Tests for LogCreateRequest schema."""

    def test_valid_watched_where(self):
        """Test valid watched_where values."""
        valid_values = ["cinema", "streaming", "homeVideo", "tv", "other"]
        for value in valid_values:
            request = LogCreateRequest(
                tmdb_id=12345,
                date_watched=date(2023, 10, 1),
                watched_where=value
            )
            assert request.watched_where == value

    def test_invalid_watched_where(self):
        """Test invalid watched_where raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LogCreateRequest(
                tmdb_id=12345,
                date_watched=date(2023, 10, 1),
                watched_where="invalid_value"
            )
        
        assert "watched_where must be one of" in str(exc_info.value)

    def test_default_watched_where(self):
        """Test default watched_where is 'other'."""
        request = LogCreateRequest(
            tmdb_id=12345,
            date_watched=date(2023, 10, 1)
        )
        assert request.watched_where == "other"


class TestLogUpdateRequest:
    """Tests for LogUpdateRequest schema."""

    def test_valid_watched_where(self):
        """Test valid watched_where values."""
        request = LogUpdateRequest(watched_where="cinema")
        assert request.watched_where == "cinema"

    def test_watched_where_none_is_valid(self):
        """Test watched_where can be None."""
        request = LogUpdateRequest(watched_where=None)
        assert request.watched_where is None

    def test_invalid_watched_where(self):
        """Test invalid watched_where raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LogUpdateRequest(watched_where="invalid")
        
        assert "watched_where must be one of" in str(exc_info.value)

    def test_empty_update_request(self):
        """Test empty update request is valid."""
        request = LogUpdateRequest()
        assert request.date_watched is None
        assert request.viewing_notes is None
        assert request.watched_where is None


class TestLogListRequest:
    """Tests for LogListRequest schema."""

    def test_valid_sort_by(self):
        """Test valid sort_by values."""
        valid_values = ["dateWatched", "watchedWhere"]
        for value in valid_values:
            request = LogListRequest(sort_by=value)
            assert request.sort_by == value

    def test_invalid_sort_by(self):
        """Test invalid sort_by raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LogListRequest(sort_by="invalidField")
        
        assert "sort_by must be one of" in str(exc_info.value)

    def test_valid_sort_order(self):
        """Test valid sort_order values."""
        request_asc = LogListRequest(sort_order="asc")
        assert request_asc.sort_order == "asc"
        
        request_desc = LogListRequest(sort_order="desc")
        assert request_desc.sort_order == "desc"

    def test_invalid_sort_order(self):
        """Test invalid sort_order raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LogListRequest(sort_order="random")
        
        assert "sort_order must be either 'asc' or 'desc'" in str(exc_info.value)

    def test_valid_watched_where_filter(self):
        """Test valid watched_where filter values."""
        request = LogListRequest(watched_where="cinema")
        assert request.watched_where == "cinema"

    def test_watched_where_filter_none_is_valid(self):
        """Test watched_where filter can be None."""
        request = LogListRequest(watched_where=None)
        assert request.watched_where is None

    def test_invalid_watched_where_filter(self):
        """Test invalid watched_where filter raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LogListRequest(watched_where="invalid")
        
        assert "watched_where must be one of" in str(exc_info.value)

    def test_valid_date_range(self):
        """Test valid date range."""
        request = LogListRequest(
            date_watched_from=date(2023, 1, 1),
            date_watched_to=date(2023, 12, 31)
        )
        assert request.date_watched_from == date(2023, 1, 1)
        assert request.date_watched_to == date(2023, 12, 31)

    def test_invalid_date_range(self):
        """Test invalid date range (from > to) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LogListRequest(
                date_watched_from=date(2023, 12, 31),
                date_watched_to=date(2023, 1, 1)
            )
        
        assert "date_watched_from cannot be after date_watched_to" in str(exc_info.value)

    def test_only_date_from_is_valid(self):
        """Test only date_watched_from without date_watched_to is valid."""
        request = LogListRequest(date_watched_from=date(2023, 1, 1))
        assert request.date_watched_from == date(2023, 1, 1)
        assert request.date_watched_to is None

    def test_only_date_to_is_valid(self):
        """Test only date_watched_to without date_watched_from is valid."""
        request = LogListRequest(date_watched_to=date(2023, 12, 31))
        assert request.date_watched_from is None
        assert request.date_watched_to == date(2023, 12, 31)

    def test_default_values(self):
        """Test default values for LogListRequest."""
        request = LogListRequest()
        assert request.sort_by == "dateWatched"
        assert request.sort_order == "desc"
        assert request.watched_where is None
        assert request.date_watched_from is None
        assert request.date_watched_to is None
