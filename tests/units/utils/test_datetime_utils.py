from datetime import date, datetime, timezone

from app.utils.datetime_utils import date_end_utc, date_start_utc, to_utc_datetime


class TestDateTimeUtils:
    def test_date_start_utc_returns_midnight(self):
        result = date_start_utc(date(2024, 1, 2))

        assert result == datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_date_end_utc_returns_end_of_day(self):
        result = date_end_utc(date(2024, 1, 2))

        assert result == datetime(2024, 1, 2, 23, 59, 59, 999999, tzinfo=timezone.utc)

    def test_to_utc_datetime_with_date_uses_start_of_day(self):
        result = to_utc_datetime(date(2024, 1, 2))

        assert result == datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_to_utc_datetime_with_naive_datetime_sets_utc_timezone(self):
        naive_datetime = datetime(2024, 1, 2, 12, 30, 45, 123456)

        result = to_utc_datetime(naive_datetime)

        assert result == datetime(2024, 1, 2, 12, 30, 45, 123456, tzinfo=timezone.utc)

    def test_to_utc_datetime_with_aware_datetime_returns_same_instance(self):
        aware_datetime = datetime(2024, 1, 2, 12, 30, 45, 123456, tzinfo=timezone.utc)

        result = to_utc_datetime(aware_datetime)

        assert result is aware_datetime
