from datetime import UTC, date, datetime, time


def date_start_utc(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def date_end_utc(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return date_start_utc(value)
