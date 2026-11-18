"""Date helpers. US federal holidays are computed by rule, no outside list."""

from datetime import date, timedelta
from functools import cache


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _rules(year: int) -> list[tuple[date, str]]:
    return [
        (_observed(date(year, 1, 1)), "New Year's Day"),
        (_nth_weekday(year, 1, 0, 3), "Martin Luther King Jr. Day"),
        (_nth_weekday(year, 2, 0, 3), "Washington's Birthday"),
        (_last_weekday(year, 5, 0), "Memorial Day"),
        (_observed(date(year, 6, 19)), "Juneteenth"),
        (_observed(date(year, 7, 4)), "Independence Day"),
        (_nth_weekday(year, 9, 0, 1), "Labor Day"),
        (_nth_weekday(year, 10, 0, 2), "Columbus Day"),
        (_observed(date(year, 11, 11)), "Veterans Day"),
        (_nth_weekday(year, 11, 3, 4), "Thanksgiving Day"),
        (_observed(date(year, 12, 25)), "Christmas Day"),
    ]


def holidays(year: int) -> dict[date, str]:
    """Observed US federal holidays that fall in the given year."""
    out: dict[date, str] = {}
    for y in (year - 1, year, year + 1):
        for d, name in _rules(y):
            if d.year == year:
                out[d] = name
    return dict(sorted(out.items()))


@cache
def _holiday_set(year: int) -> frozenset[date]:
    return frozenset(holidays(year))


def is_holiday(d: date) -> bool:
    return d in _holiday_set(d.year)


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and not is_holiday(d)


def next_business_day(d: date) -> date:
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def add_business_days(d: date, n: int) -> date:
    d = next_business_day(d)
    for _ in range(n):
        d = next_business_day(d + timedelta(days=1))
    return d


def business_days(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if is_business_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def month_ends(start: date, months: int) -> list[date]:
    out: list[date] = []
    y, m = start.year, start.month
    for _ in range(months):
        out.append(last_day_of_month(y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


CLOSE_WINDOW_BUSINESS_DAYS = 3


def nth_business_day(year: int, month: int, n: int) -> date:
    return add_business_days(date(year, month, 1), n - 1)


@cache
def _close_end(year: int, month: int) -> date | None:
    try:
        return nth_business_day(year, month, CLOSE_WINDOW_BUSINESS_DAYS)
    except (ValueError, OverflowError):
        return None


def in_close_window(d: date) -> bool:
    """True on or before the last close day of the month."""
    end = _close_end(d.year, d.month)
    return end is not None and d <= end


def previous_period(d: date) -> str:
    if d.month == 1:
        return f"{d.year - 1}-12"
    return f"{d.year}-{d.month - 1:02d}"
