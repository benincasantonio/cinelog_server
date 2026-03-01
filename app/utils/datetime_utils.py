from datetime import date, datetime, time, timezone


def date_start_utc(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def date_end_utc(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return date_start_utc(value)
