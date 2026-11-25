from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_ist() -> datetime:
    """Return the current timezone-aware datetime in IST (UTC+05:30)."""
    return datetime.now(IST)


def from_timestamp_ist(ts: float) -> datetime:
    """Convert a POSIX timestamp into an IST-aware datetime."""
    return datetime.fromtimestamp(ts, tz=IST)


def ensure_ist(dt: datetime) -> datetime:
    """Ensure a datetime read back from SQLite retains the +05:30 IST offset."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)