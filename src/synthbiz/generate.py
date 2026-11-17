"""Generate one linked set of finance tables."""

from dataclasses import dataclass
from datetime import date, timedelta

from . import builder as bld
from .anomalies import inject
from .builder import Builder, Row, nonround
from .check import month_ends_from_lines, reconciling_items
from .dates import add_business_days, business_days, month_ends, next_business_day
from .names import customer_names, vendor_names
from .schema import TABLE_NAMES

OPENING_CASH_CENTS = 100_000_000
PAY_RATE_AP = 0.9
PAY_RATE_AR = 0.9


@dataclass(frozen=True)
class Size:
    vendors: int
    customers: int
    ap_per_month: int
    ar_per_month: int
    manual_per_month: int


SIZES = {
    "small": Size(8, 6, 12, 10, 2),
    "medium": Size(25, 20, 40, 30, 4),
    "large": Size(60, 50, 120, 90, 8),
}


@dataclass(frozen=True)
class Params:
    seed: int = 42
    months: int = 12
    size: str = "small"
    anomaly_rate: float = 0.02
    start_date: date = date(2025, 1, 1)


@dataclass
class Dataset:
    params: Params
    tables: dict[str, list[Row]]
    labels: list[dict[str, str]]
    anomaly_count: int


def _month_days(days: list[date], me: date) -> list[date]:
    return [d for d in days if d.year == me.year and d.month == me.month]


def _ap_amount(b: Builder) -> int:
    if b.rng.random() < 0.1:
        return nonround(b.rng.randint(bld.APPROVAL_LIMIT_CENTS, 2_500_000))
    return nonround(b.rng.randint(15_000, 450_000))


def _base_activity(b: Builder, size: Size, months: int, start: date) -> int:
    rng = b.rng
    days = business_days(b.start, b.end)
    last_day = days[-1]
    vendors = b.tables["vendors"]
    customers = b.tables["customers"]
    base_count = 0
    for me in month_ends(start, months):
        month_days = _month_days(days, me)
        if not month_days:
            continue
        for _ in range(size.ap_per_month):
            inv = b.ap_invoice(
                rng.choice(month_days), rng.choice(vendors), _ap_amount(b)
            )
            base_count += 1
            due = date.fromisoformat(inv["due_date"])
            pay = next_business_day(due + timedelta(days=rng.randint(-3, 3)))
            if pay <= last_day and rng.random() < PAY_RATE_AP:
                b.ap_payment(inv, pay)
        for _ in range(size.ar_per_month):
            cust = rng.choice(customers)
            ar = b.ar_invoice(
                rng.choice(month_days), cust, nonround(rng.randint(50_000, 3_000_000))
            )
            base_count += 1
            due = date.fromisoformat(ar["due_date"])
            rec = next_business_day(due + timedelta(days=rng.randint(-5, 10)))
            if rec <= last_day and rng.random() < PAY_RATE_AR:
                b.ar_receipt(ar, rec)
        for _ in range(size.manual_per_month):
            account = rng.choice(["6100", "6200", "6900"])
            b.manual_entry(
                rng.choice(month_days), nonround(rng.randint(5_000, 300_000)), account
            )
            base_count += 1
    return base_count


def _sort(tables: dict[str, list[Row]]) -> None:
    keys = {
        "journal_lines": ("posting_date", "line_id"),
        "ap_invoices": ("invoice_date", "invoice_id"),
        "ap_payments": ("payment_date", "payment_id"),
        "ar_invoices": ("invoice_date", "invoice_id"),
        "ar_receipts": ("receipt_date", "receipt_id"),
        "bank_transactions": ("bank_date", "bank_txn_id"),
    }
    for name, (k1, k2) in keys.items():
        tables[name].sort(key=lambda r: (r[k1], r[k2]))


def generate(params: Params) -> Dataset:
    if params.size not in SIZES:
        raise ValueError(f"size must be one of {sorted(SIZES)}")
    if params.months < 1:
        raise ValueError("months must be at least 1")
    size = SIZES[params.size]
    start = params.start_date
    end = month_ends(start, params.months)[-1]
    b = Builder(params.seed, start, end)
    for name in TABLE_NAMES:
        b.table(name)
    b.tables["chart_of_accounts"].extend(
        {
            "account_id": a,
            "account_name": n,
            "account_type": t,
            "normal_balance": nb,
            "role": r,
        }
        for a, n, t, nb, r in bld.CHART
    )
    for i, name in enumerate(vendor_names(b.rng, size.vendors), start=1):
        b.tables["vendors"].append(
            {
                "vendor_id": f"V-{i:04d}",
                "vendor_name": name,
                "category": b.rng.choice(bld.CATEGORIES)[0],
                "terms_days": b.rng.choice([30, 30, 45]),
            }
        )
    b.base_vendors = len(b.tables["vendors"])
    for i, name in enumerate(customer_names(b.rng, size.customers), start=1):
        b.tables["customers"].append(
            {
                "customer_id": f"C-{i:04d}",
                "customer_name": name,
                "terms_days": b.rng.choice([30, 30, 45]),
            }
        )
    first_day = add_business_days(start, 0)
    je_id, _ = b.post(
        first_day,
        [(bld.CASH, OPENING_CASH_CENTS, 0), (bld.EQUITY, 0, OPENING_CASH_CENTS)],
        "Opening capital",
        "OPENING",
        "",
        "CONTROLLER_1",
        "OWNER_1",
    )
    b.table("bank_transactions").append(
        {
            "bank_txn_id": b.next_id("BK"),
            "bank_date": first_day.isoformat(),
            "amount_cents": OPENING_CASH_CENTS,
            "ref_type": "OPENING",
            "ref_id": je_id,
        }
    )
    base_count = _base_activity(b, size, params.months, start)
    anomaly_count = round(params.anomaly_rate * base_count)
    inject(b, anomaly_count)
    _sort(b.tables)
    ends = month_ends_from_lines(b.tables["journal_lines"])
    b.tables["reconciling_items"] = reconciling_items(b.tables, ends)
    return Dataset(params, b.tables, b.labels, anomaly_count)
