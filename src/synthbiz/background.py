"""Legitimate unlabeled activity that looks a little like anomalies."""

from datetime import date, timedelta
from typing import TYPE_CHECKING

from .builder import Builder, Row, nonround
from .dates import (
    CLOSE_WINDOW_BUSINESS_DAYS,
    business_days,
    holidays,
    month_ends,
    next_business_day,
    nth_business_day,
    previous_period,
)

if TYPE_CHECKING:
    from .generate import Size

BACKGROUND_KINDS = (
    "close_window_accrual",
    "human_weekend_close",
    "occasional_poster",
    "recurring_fixed_invoice",
    "round_rent_accrual",
    "round_retainer_invoice",
    "system_batch_weekend",
    "system_recurring",
)
GL_USERS = ["GL_ACCOUNTANT_1", "GL_ACCOUNTANT_2"]
ACCOUNTS = ["6100", "6200", "6900"]
QUARTER_END_MONTHS = (3, 6, 9, 12)
LAST_DAYS = 7


def _post(
    b: Builder,
    kind: str,
    d: date,
    created_by: str | None,
    approved_by: str | None,
    memo: str,
    amount: int | None = None,
    account: str | None = None,
    period: str | None = None,
) -> None:
    _, line_id = b.manual_entry(
        d,
        amount or nonround(b.rng.randint(5_000, 300_000)),
        account or b.rng.choice(ACCOUNTS),
        created_by,
        approved_by,
        period,
        memo,
    )
    b.mark_background("journal_lines", line_id, kind)


def _last_days(me: date, start: date) -> list[date]:
    days = [me - timedelta(days=k) for k in range(LAST_DAYS)]
    return [d for d in days if d >= start]


def _in_month(days: list[date], me: date) -> list[date]:
    return [d for d in days if (d.year, d.month) == (me.year, me.month)]


def _system_entries(b: Builder, ends: list[date], days: list[date]) -> None:
    rng = b.rng
    for me in ends:
        first = me.replace(day=1)
        weekend = [
            d
            for d in (first + timedelta(days=k) for k in range(me.day))
            if d >= b.start and d.weekday() >= 5
        ]
        if weekend:
            _post(
                b,
                "system_batch_weekend",
                rng.choice(weekend),
                "SYSTEM_BATCH",
                None,
                "Scheduled accrual batch",
                account="6100",
            )
        month_days = _in_month(days, me)
        for _ in range(2 if month_days else 0):
            _post(
                b,
                "system_recurring",
                rng.choice(month_days),
                "SYSTEM_RECURRING",
                None,
                "Recurring accrual",
                account="6100",
            )
    for year in range(b.start.year, b.end.year + 1):
        for d in holidays(year):
            if b.start <= d <= b.end:
                _post(
                    b,
                    "system_batch_weekend",
                    d,
                    "SYSTEM_BATCH",
                    None,
                    "Scheduled accrual batch",
                    account="6100",
                )


def _close_entries(b: Builder, size: "Size", ends: list[date]) -> None:
    rng = b.rng
    for me in ends[1:]:
        for _ in range(max(1, size.manual_per_month // 4)):
            n = rng.randint(1, CLOSE_WINDOW_BUSINESS_DAYS)
            d = nth_business_day(me.year, me.month, n)
            _post(
                b,
                "close_window_accrual",
                d,
                rng.choice(GL_USERS),
                "CONTROLLER_1",
                "Accrual",
                period=previous_period(d),
            )


def _people_entries(b: Builder, ends: list[date], days: list[date]) -> None:
    rng = b.rng
    day_set = set(days)
    for me in ends:
        if me.month not in QUARTER_END_MONTHS:
            continue
        window = _last_days(me, b.start)
        weekend = [d for d in window if d.weekday() >= 5]
        if weekend:
            _post(
                b,
                "human_weekend_close",
                rng.choice(weekend),
                rng.choice(GL_USERS),
                "CONTROLLER_1",
                "Accrual",
            )
        work = [d for d in window if d in day_set]
        if work:
            _post(
                b,
                "occasional_poster",
                rng.choice(work),
                "CFO_1",
                "OWNER_1",
                "Accrual",
            )
    for year in range(b.start.year, b.end.year + 1):
        work = [d for d in days if d.year == year]
        if work:
            _post(
                b,
                "occasional_poster",
                rng.choice(work),
                "TAX_ACCOUNTANT_1",
                "CONTROLLER_1",
                "Accrual",
            )


def _rent(b: Builder, ends: list[date], days: list[date]) -> None:
    amount = b.rng.randint(4, 12) * 100_000
    for me in ends:
        month_days = _in_month(days, me)
        if month_days:
            _post(
                b,
                "round_rent_accrual",
                month_days[0],
                "GL_ACCOUNTANT_1",
                "CONTROLLER_1",
                "Rent accrual",
                amount=amount,
                account="6900",
            )


def _pick_vendor(b: Builder, category: str, avoid: str = "") -> Row:
    base = b.tables["vendors"][: b.base_vendors]
    other = [v for v in base if v["vendor_id"] != avoid] or base
    return b.rng.choice([v for v in other if v["category"] == category] or other)


def _pay_when_due(b: Builder, inv: Row, last_day: date) -> None:
    pay = next_business_day(date.fromisoformat(inv["due_date"]))
    if pay <= last_day:
        b.ap_payment(inv, pay)


def _retainer(b: Builder, ends: list[date], days: list[date]) -> Row:
    vendor = _pick_vendor(b, "Services")
    amount = b.rng.randint(2, 4) * 100_000
    for me in ends:
        month_days = _in_month(days, me)
        if not month_days:
            continue
        inv = b.ap_invoice(
            b.rng.choice(month_days), vendor, amount, f"RET-{me.year}{me.month:02d}"
        )
        b.mark_background("ap_invoices", inv["invoice_id"], "round_retainer_invoice")
        _pay_when_due(b, inv, days[-1])
    return vendor


def _weekly(b: Builder, retainer: Row, days: list[date]) -> None:
    rng = b.rng
    vendor = _pick_vendor(b, "Freight", retainer["vendor_id"])
    amount = nonround(rng.randint(30_000, 120_000))
    weekday = rng.randint(0, 4)
    number = rng.randint(100, 999)
    d = b.start
    while d <= b.end:
        if d.weekday() == weekday:
            inv_date = next_business_day(d)
            if inv_date <= days[-1]:
                inv = b.ap_invoice(inv_date, vendor, amount, f"FR-{number:05d}")
                number += 1
                b.mark_background(
                    "ap_invoices", inv["invoice_id"], "recurring_fixed_invoice"
                )
                _pay_when_due(b, inv, days[-1])
        d += timedelta(days=1)


def add_background(b: Builder, size: "Size", months: int, start: date) -> None:
    days = business_days(b.start, b.end)
    ends = month_ends(start, months)
    _system_entries(b, ends, days)
    _close_entries(b, size, ends)
    _people_entries(b, ends, days)
    _rent(b, ends, days)
    retainer = _retainer(b, ends, days)
    _weekly(b, retainer, days)
