from datetime import UTC, date, datetime, time


def date_start_utc(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def date_end_utc(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return date_start_utc(value)


def parse_iso_date(value: str | None, fmt: str = "%Y-%m-%d") -> datetime | None:
    """Parse a date string into a naive ``datetime``, returning ``None`` on empty or malformed input."""
    if not value:
        return None

    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None
