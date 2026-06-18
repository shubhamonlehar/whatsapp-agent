from datetime import datetime, timedelta, timezone


INDIA_OFFSET = timedelta(hours=5, minutes=30)
INDIA_TIMEZONE = timezone(INDIA_OFFSET, name="IST")


def to_india_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(INDIA_TIMEZONE)


def india_isoformat(value: datetime) -> str:
    return to_india_time(value).isoformat()


def india_wall_clock_timestamp() -> str:
    value = datetime.now(INDIA_TIMEZONE).replace(tzinfo=timezone.utc)
    return str(int(value.timestamp()))
