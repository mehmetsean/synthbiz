"""Inject labeled anomalies. Every anomaly still posts to the ledger correctly."""

import random
from datetime import date, timedelta

from .builder import APPROVAL_LIMIT_CENTS, Builder, Row, nonround
from .dates import (
    add_business_days,
    business_days,
    holidays,
    in_close_window,
    is_business_day,
    previous_period,
)
from .names import name_variant

ANOMALY_TYPES = [
    "exact_duplicate_payment",
    "near_duplicate_payment",
    "typo_duplicate_payment",
    "split_invoice",
    "round_amount_entry",
    "weekend_posting",
    "holiday_posting",
    "unusual_user",
    "missing_approval",
    "out_of_period_entry",
]
UNUSUAL_USERS = ["IT_ADMIN_1", "TEMP_USER_1"]


def _calendar(b: Builder) -> tuple[list[date], list[date], list[date]]:
    work: list[date] = []
    weekend: list[date] = []
    holiday: list[date] = []
    d = b.start
    while d <= b.end:
        if d.weekday() >= 5:
            weekend.append(d)
        elif is_business_day(d):
            work.append(d)
        else:
            holiday.append(d)
        d += timedelta(days=1)
    return work, weekend, holiday


def _paid_invoice(b: Builder, work: list[date]) -> tuple[Row, Row]:
    rng = b.rng
    vendor = rng.choice(b.tables["vendors"][: b.base_vendors])
    early = work[: max(1, int(len(work) * 0.7))]
    inv = b.ap_invoice(
        rng.choice(early), vendor, nonround(rng.randint(20_000, 450_000))
    )
    pay_date = min(
        add_business_days(date.fromisoformat(inv["invoice_date"]), rng.randint(3, 12)),
        work[-1],
    )
    return inv, b.ap_payment(inv, pay_date)


def _later(b: Builder, d: date, work: list[date]) -> date:
    return min(add_business_days(d + timedelta(days=1), b.rng.randint(0, 2)), work[-1])


def _exact_duplicate(b: Builder, work: list[date]) -> None:
    inv, pay = _paid_invoice(b, work)
    dup = b.ap_payment(inv, _later(b, date.fromisoformat(pay["payment_date"]), work))
    b.label(
        "ap_payments",
        dup["payment_id"],
        "exact_duplicate_payment",
        f"Same vendor, invoice and amount as {pay['payment_id']}",
    )


def _near_duplicate(b: Builder, work: list[date]) -> None:
    inv, pay = _paid_invoice(b, work)
    vendors = b.tables["vendors"]
    original = next(v for v in vendors if v["vendor_id"] == inv["vendor_id"])
    variant: Row = {
        "vendor_id": f"V-{len(vendors) + 1:04d}",
        "vendor_name": name_variant(original["vendor_name"], b.rng),
        "category": original["category"],
        "terms_days": original["terms_days"],
    }
    vendors.append(variant)
    twin = b.ap_invoice(
        date.fromisoformat(inv["invoice_date"]),
        variant,
        inv["amount_cents"],
        inv["invoice_number"],
    )
    dup = b.ap_payment(twin, _later(b, date.fromisoformat(pay["payment_date"]), work))
    b.label(
        "ap_payments",
        dup["payment_id"],
        "near_duplicate_payment",
        f"Invoice {inv['invoice_number']} paid again under {variant['vendor_id']} "
        f"({variant['vendor_name']}), similar to {original['vendor_id']}; "
        f"first paid as {pay['payment_id']}",
    )


def _typo(number: str, rng: random.Random) -> str:
    options: set[str] = set()
    for i in range(len(number)):
        options.add(number[:i] + number[i + 1 :])
        options.add(number[: i + 1] + number[i:])
        if i + 1 < len(number) and number[i] != number[i + 1]:
            options.add(number[:i] + number[i + 1] + number[i] + number[i + 2 :])
    options.discard(number)
    options.discard("")
    return rng.choice(sorted(options))


def _typo_duplicate(b: Builder, work: list[date]) -> None:
    inv, pay = _paid_invoice(b, work)
    vendor = next(v for v in b.tables["vendors"] if v["vendor_id"] == inv["vendor_id"])
    number = _typo(inv["invoice_number"], b.rng)
    twin = b.ap_invoice(
        date.fromisoformat(inv["invoice_date"]), vendor, inv["amount_cents"], number
    )
    dup = b.ap_payment(twin, _later(b, date.fromisoformat(pay["payment_date"]), work))
    b.label(
        "ap_payments",
        dup["payment_id"],
        "typo_duplicate_payment",
        f"Invoice {inv['invoice_number']} entered again as {number} under "
        f"{vendor['vendor_id']} with the same amount; first paid as "
        f"{pay['payment_id']}",
    )


def _split_invoice(b: Builder, work: list[date]) -> None:
    rng = b.rng
    vendor = rng.choice(b.tables["vendors"][: b.base_vendors])
    d = rng.choice(work)
    parts = [
        b.ap_invoice(d, vendor, nonround(rng.randint(460_000, 499_000)))
        for _ in range(rng.randint(2, 3))
    ]
    total = sum(p["amount_cents"] for p in parts)
    ids = ", ".join(p["invoice_id"] for p in parts)
    b.label(
        "ap_invoices",
        parts[0]["invoice_id"],
        "split_invoice",
        f"{len(parts)} invoices from {vendor['vendor_id']} on {d.isoformat()} "
        f"({ids}) each under the {APPROVAL_LIMIT_CENTS} cent limit, "
        f"total {total} cents",
    )


def _journal_anomaly(
    b: Builder, kind: str, work: list[date], weekend: list[date], holiday: list[date]
) -> None:
    rng = b.rng
    d = rng.choice(work)
    amount = nonround(rng.randint(5_000, 300_000))
    note = "Manual accrual"
    created_by: str | None = None
    approved_by: str | None = "CONTROLLER_1"
    period: str | None = None
    if kind == "round_amount_entry":
        amount = rng.randint(1, 50) * 100_000
        note = f"Manual accrual of exactly {amount} cents"
    elif kind == "weekend_posting":
        d = rng.choice(weekend)
        note = f"Manual accrual posted on a {d.strftime('%A')}"
    elif kind == "holiday_posting":
        d = rng.choice(holiday)
        note = f"Manual accrual posted on {holidays(d.year)[d]}"
    elif kind == "unusual_user":
        created_by = rng.choice(UNUSUAL_USERS)
        note = f"Manual accrual posted by {created_by}, not a usual poster"
    elif kind == "missing_approval":
        approved_by = None
        note = "Manual accrual with no approver"
    else:
        d = rng.choice([x for x in work if not in_close_window(x)] or work)
        period = previous_period(d)
        note = f"Manual accrual posted {d.isoformat()} to period {period}"
    je_id, line_id = b.manual_entry(
        d,
        amount,
        rng.choice(["6100", "6200", "6900"]),
        created_by=created_by,
        approved_by=approved_by,
        period=period,
    )
    b.label("journal_lines", line_id, kind, f"{note} ({je_id})")


def inject(b: Builder, count: int) -> None:
    work, weekend, holiday = _calendar(b)
    if not work:
        work = business_days(b.start, b.end)
    skip = set()
    if not holiday:
        skip.add("holiday_posting")
    if not weekend:
        skip.add("weekend_posting")
    kinds = [k for k in ANOMALY_TYPES if k not in skip]
    for i in range(count):
        kind = kinds[i % len(kinds)]
        if kind == "exact_duplicate_payment":
            _exact_duplicate(b, work)
        elif kind == "near_duplicate_payment":
            _near_duplicate(b, work)
        elif kind == "typo_duplicate_payment":
            _typo_duplicate(b, work)
        elif kind == "split_invoice":
            _split_invoice(b, work)
        else:
            _journal_anomaly(b, kind, work, weekend, holiday)
