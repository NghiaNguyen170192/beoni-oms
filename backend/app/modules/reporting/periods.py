from datetime import date, timedelta
from enum import Enum

from app.core.errors import Invalid
from app.modules.reporting.errors import RangeTooLong

MAX_DAYS = 366


class PeriodPreset(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"


class GroupBy(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def resolve_preset(preset: PeriodPreset, today: date) -> tuple[date, date]:
    """Inclusive business dates for a preset, relative to `today`."""
    if preset == PeriodPreset.TODAY:
        return today, today
    if preset == PeriodPreset.YESTERDAY:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if preset == PeriodPreset.LAST_7_DAYS:
        return today - timedelta(days=6), today
    if preset == PeriodPreset.THIS_MONTH:
        return today.replace(day=1), today
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=1), last_prev


def previous_period(date_from: date, date_to: date) -> tuple[date, date]:
    """The equal-length period immediately before `date_from`."""
    length = (date_to - date_from).days
    previous_to = date_from - timedelta(days=1)
    return previous_to - timedelta(days=length), previous_to


def check_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise Invalid("date_to is before date_from")
    if (date_to - date_from).days + 1 > MAX_DAYS:
        raise RangeTooLong()
