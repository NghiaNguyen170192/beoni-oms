from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def period_bounds(
    start: date, end: date, timezone_name: str
) -> tuple[datetime, datetime]:
    """Half-open UTC interval covering whole business-timezone days, inclusive."""
    zone = ZoneInfo(timezone_name)
    start_local = datetime.combine(start, time.min, tzinfo=zone)
    end_local = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone)
    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(
        ZoneInfo("UTC")
    )


def noon_on(day: date, timezone_name: str) -> datetime:
    """A timestamp that falls on `day` in the business timezone."""
    return datetime.combine(day, time(12, 0), tzinfo=ZoneInfo(timezone_name))
