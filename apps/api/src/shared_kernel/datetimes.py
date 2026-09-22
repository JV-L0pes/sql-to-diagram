from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes read back from SQLite (which drops tzinfo) to aware UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
