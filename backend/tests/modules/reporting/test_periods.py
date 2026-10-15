from datetime import date

import pytest

from app.core.errors import Invalid
from app.modules.reporting.errors import RangeTooLong
from app.modules.reporting.periods import (
    PeriodPreset,
    check_range,
    previous_period,
    resolve_preset,
)


def test_presets_are_inclusive_business_dates() -> None:
    today = date(2026, 10, 15)
    assert resolve_preset(PeriodPreset.TODAY, today) == (today, today)
    assert resolve_preset(PeriodPreset.YESTERDAY, today) == (
        date(2026, 10, 14),
        date(2026, 10, 14),
    )
    assert resolve_preset(PeriodPreset.LAST_7_DAYS, today) == (date(2026, 10, 9), today)
    assert resolve_preset(PeriodPreset.THIS_MONTH, today) == (date(2026, 10, 1), today)
    assert resolve_preset(PeriodPreset.LAST_MONTH, today) == (
        date(2026, 9, 1),
        date(2026, 9, 30),
    )


def test_previous_period_has_equal_length() -> None:
    start, end = previous_period(date(2026, 10, 1), date(2026, 10, 15))
    assert (end - start).days == 14
    assert end == date(2026, 9, 30)


def test_range_cap() -> None:
    check_range(date(2026, 1, 1), date(2026, 12, 31))
    with pytest.raises(RangeTooLong):
        check_range(date(2026, 1, 1), date(2027, 1, 2))
    with pytest.raises(Invalid):
        check_range(date(2026, 2, 2), date(2026, 2, 1))
