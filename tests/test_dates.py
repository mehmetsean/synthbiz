from datetime import date

from synthbiz.dates import (
    add_business_days,
    business_days,
    holidays,
    is_business_day,
    is_holiday,
    month_ends,
    next_business_day,
)


def test_fixed_holidays_2025() -> None:
    h = holidays(2025)
    assert h[date(2025, 1, 1)] == "New Year's Day"
    assert date(2025, 1, 20) in h  # third Monday of January
    assert date(2025, 2, 17) in h
    assert date(2025, 5, 26) in h  # last Monday of May
    assert date(2025, 6, 19) in h
    assert date(2025, 7, 4) in h
    assert date(2025, 9, 1) in h
    assert date(2025, 10, 13) in h
    assert date(2025, 11, 11) in h
    assert date(2025, 11, 27) in h  # fourth Thursday of November
    assert date(2025, 12, 25) in h
    assert len(h) == 11


def test_observed_shift() -> None:
    # July 4, 2026 is a Saturday, observed Friday July 3.
    assert date(2026, 7, 3) in holidays(2026)
    assert date(2026, 7, 4) not in holidays(2026)
    # Nov 11, 2029 is a Sunday, observed Monday Nov 12.
    assert date(2029, 11, 12) in holidays(2029)


def test_new_year_observed_in_previous_year() -> None:
    # Jan 1, 2022 is a Saturday, observed Friday Dec 31, 2021.
    assert not is_business_day(date(2021, 12, 31))


def test_business_days() -> None:
    assert is_business_day(date(2025, 1, 2))
    assert not is_business_day(date(2025, 1, 1))
    assert not is_business_day(date(2025, 1, 4))  # Saturday
    assert next_business_day(date(2025, 1, 1)) == date(2025, 1, 2)
    assert next_business_day(date(2025, 1, 2)) == date(2025, 1, 2)
    assert add_business_days(date(2025, 1, 3), 1) == date(2025, 1, 6)
    assert add_business_days(date(2025, 1, 3), 0) == date(2025, 1, 3)


def test_business_days_range() -> None:
    days = business_days(date(2025, 1, 1), date(2025, 1, 31))
    assert days[0] == date(2025, 1, 2)
    assert len(days) == 21
    assert days == sorted(days)


def test_month_ends() -> None:
    ends = month_ends(date(2025, 11, 5), 3)
    assert ends == [date(2025, 11, 30), date(2025, 12, 31), date(2026, 1, 31)]
    assert month_ends(date(2024, 2, 1), 1) == [date(2024, 2, 29)]


def test_close_window_helpers() -> None:
    from synthbiz.dates import (
        CLOSE_WINDOW_BUSINESS_DAYS,
        in_close_window,
        nth_business_day,
        previous_period,
    )

    assert CLOSE_WINDOW_BUSINESS_DAYS == 3
    assert nth_business_day(2025, 1, 3) == date(2025, 1, 6)
    assert nth_business_day(2025, 3, 3) == date(2025, 3, 5)
    assert in_close_window(date(2025, 3, 5))
    assert not in_close_window(date(2025, 3, 6))
    assert in_close_window(date(2025, 3, 1))
    assert in_close_window(date(2025, 1, 2))
    assert not in_close_window(date(2025, 1, 7))
    assert not in_close_window(date(9999, 12, 31))
    assert not in_close_window(date(1, 1, 5))
    assert previous_period(date(2025, 1, 2)) == "2024-12"
    assert previous_period(date(2025, 3, 5)) == "2025-02"


def test_finance_juneteenth_in_every_year() -> None:
    # stated limit
    assert is_holiday(date(2020, 6, 19))
