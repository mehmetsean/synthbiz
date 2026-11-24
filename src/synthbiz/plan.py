"""Budget lines and fixed asset, loan and equity entries."""

import random
from datetime import date
from typing import Any

from .builder import CASH, Builder
from .dates import business_days, month_ends

Row = dict[str, Any]

BUDGET_VARIANCE_RATE = 0.1
BUDGET_MIN_ACTUAL_CENTS = 100_000
PCT_CHOICES = [1000, 1500, 2000, 2500, 3000]
AMOUNT_CHOICES = [5_000, 10_000, 25_000, 50_000]

PL_TYPES = ("REVENUE", "EXPENSE")


def _pl_accounts(coa: list[Row]) -> list[str]:
    return sorted(str(a["account_id"]) for a in coa if a["account_type"] in PL_TYPES)


def actual_by_cell(coa: list[Row], lines: list[Row]) -> dict[tuple[str, str], int]:
    """Result per (period, account) for P&L accounts, positive for normal side."""
    types = {str(a["account_id"]): str(a["account_type"]) for a in coa}
    totals: dict[tuple[str, str], int] = {}
    for r in lines:
        account = str(r["account_id"])
        if account not in types:
            raise ValueError(f"journal line account {account} is not in the chart")
        if types[account] not in PL_TYPES:
            continue
        net = int(r["debit_cents"]) - int(r["credit_cents"])
        sign = 1 if types[account] == "EXPENSE" else -1
        key = (str(r["period"]), account)
        totals[key] = totals.get(key, 0) + sign * net
    periods = sorted({str(r["period"]) for r in lines})
    return {(p, a): totals.get((p, a), 0) for p in periods for a in _pl_accounts(coa)}


def _delta(rng: random.Random, kind: int, actual: int) -> tuple[str, int, str]:
    sign = rng.choice([1, -1])
    word = "above" if sign > 0 else "below"
    if kind == 0:
        bp = rng.choice(PCT_CHOICES)
        text = f"budget is {bp} basis points {word} actual"
        return "budget_variance_pct", sign * (actual * bp // 10_000), text
    cents = rng.choice(AMOUNT_CHOICES)
    text = f"budget is a fixed amount {word} actual"
    return "budget_variance_amount", sign * cents, text


def plan_budget(
    coa: list[Row], lines: list[Row], seed: int
) -> tuple[list[Row], list[Row]]:
    """Budget rows equal to the actual result, then a planted set of changed cells."""
    actual = actual_by_cell(coa, lines)
    cells = sorted(actual)
    ids = {cell: f"BL-{n:06d}" for n, cell in enumerate(cells, start=1)}
    eligible = [c for c in cells if actual[c] >= BUDGET_MIN_ACTUAL_CENTS]
    count = max(1, round(BUDGET_VARIANCE_RATE * len(eligible))) if eligible else 0
    rng = random.Random(f"budget:{seed}")
    chosen = sorted(rng.sample(eligible, count))
    planted: dict[tuple[str, str], int] = {}
    labels: list[Row] = []
    for n, cell in enumerate(chosen):
        kind, delta, text = _delta(rng, n % 2, actual[cell])
        planted[cell] = delta
        labels.append(
            {
                "table": "budget_lines",
                "row_id": ids[cell],
                "anomaly_type": kind,
                "details": f"{text}, delta_cents={delta}",
            }
        )
    rows = [
        {
            "budget_id": ids[c],
            "period": c[0],
            "account_id": c[1],
            "amount_cents": actual[c] + planted.get(c, 0),
        }
        for c in cells
    ]
    return rows, labels


FIXED_ASSET = "1500"
ACCUM_DEPRECIATION = "1590"
LOAN = "2500"
CONTRIBUTIONS = "3100"
DEPRECIATION = "6500"

PLAN_CHART: list[tuple[str, str, str, str, str]] = [
    (FIXED_ASSET, "Equipment", "ASSET", "DEBIT", "FIXED_ASSET"),
    (
        ACCUM_DEPRECIATION,
        "Accumulated Depreciation",
        "ASSET",
        "CREDIT",
        "ACCUM_DEPRECIATION",
    ),
    (LOAN, "Bank Loan Payable", "LIABILITY", "CREDIT", "LOAN"),
    (CONTRIBUTIONS, "Owner Contributions", "EQUITY", "CREDIT", "EQUITY_CONTRIBUTION"),
    (DEPRECIATION, "Depreciation Expense", "EXPENSE", "DEBIT", "DEPRECIATION"),
]

EQUIPMENT_BUYS = [(0, 24_000_000), (6, 9_000_000)]
LOAN_DRAW_MONTH = 1
LOAN_DRAW_CENTS = 30_000_000
REPAY_FIRST_MONTH = 2
REPAY_CENTS = 1_000_000
CONTRIBUTION_MONTH = 3
CONTRIBUTION_CENTS = 5_000_000
LIFE_MONTHS = 60

KIND_ORDER = [
    "EQUIPMENT_PURCHASE",
    "LOAN_DRAW",
    "OWNER_CONTRIBUTION",
    "DEPRECIATION",
    "LOAN_REPAYMENT",
]

Event = tuple[int, str, int]


def depreciation_for(cost: int, age: int) -> int:
    """Straight line charge in the given month after purchase, 1 is the first."""
    if age < 1 or age > LIFE_MONTHS:
        return 0
    monthly = cost // LIFE_MONTHS
    return cost - monthly * (LIFE_MONTHS - 1) if age == LIFE_MONTHS else monthly


def cash_schedule(months: int) -> list[Event]:
    """Month index, kind and cents of each fixed asset, loan and equity event."""
    events: list[Event] = []
    for first, cost in EQUIPMENT_BUYS:
        if first < months:
            events.append((first, "EQUIPMENT_PURCHASE", cost))
    if LOAN_DRAW_MONTH < months:
        events.append((LOAN_DRAW_MONTH, "LOAN_DRAW", LOAN_DRAW_CENTS))
    if CONTRIBUTION_MONTH < months:
        events.append((CONTRIBUTION_MONTH, "OWNER_CONTRIBUTION", CONTRIBUTION_CENTS))
    balance = LOAN_DRAW_CENTS if LOAN_DRAW_MONTH < months else 0
    for m in range(months):
        charge = sum(
            depreciation_for(cost, m - first) for first, cost in EQUIPMENT_BUYS
        )
        if charge:
            events.append((m, "DEPRECIATION", charge))
        if m >= REPAY_FIRST_MONTH and balance:
            paid = min(REPAY_CENTS, balance)
            balance -= paid
            events.append((m, "LOAN_REPAYMENT", paid))
    events.sort(key=lambda e: (e[0], KIND_ORDER.index(e[1])))
    return events


def _posting(kind: str, cents: int) -> tuple[list[tuple[str, int, int]], str, int]:
    """Journal lines, memo and signed bank amount for one event."""
    if kind == "EQUIPMENT_PURCHASE":
        return [(FIXED_ASSET, cents, 0), (CASH, 0, cents)], "Equipment purchase", -cents
    if kind == "LOAN_DRAW":
        return [(CASH, cents, 0), (LOAN, 0, cents)], "Loan draw", cents
    if kind == "LOAN_REPAYMENT":
        return [(LOAN, cents, 0), (CASH, 0, cents)], "Loan repayment", -cents
    if kind == "OWNER_CONTRIBUTION":
        return (
            [(CASH, cents, 0), (CONTRIBUTIONS, 0, cents)],
            "Owner contribution",
            cents,
        )
    lines = [(DEPRECIATION, cents, 0), (ACCUM_DEPRECIATION, 0, cents)]
    return lines, "Monthly depreciation", 0


def add_cash_flow_entries(b: Builder, months: int, start: date) -> None:
    """Post the schedule. Cash entries clear the bank on the same day."""
    b.tables["chart_of_accounts"].extend(
        {
            "account_id": a,
            "account_name": n,
            "account_type": t,
            "normal_balance": nb,
            "role": r,
        }
        for a, n, t, nb, r in PLAN_CHART
    )
    days = business_days(b.start, b.end)
    ends = month_ends(start, months)
    for index, kind, cents in cash_schedule(months):
        me = ends[index]
        if kind in ("DEPRECIATION", "LOAN_REPAYMENT"):
            before = [d for d in days if d <= me]
            day = before[-1] if before else days[0]
        else:
            after = [d for d in days if d >= me.replace(day=1)]
            day = after[0] if after else days[-1]
        lines, memo, bank = _posting(kind, cents)
        je_id, _ = b.post(
            day, lines, memo, "MANUAL", "", "GL_ACCOUNTANT_1", "CONTROLLER_1"
        )
        if bank:
            b.table("bank_transactions").append(
                {
                    "bank_txn_id": b.next_id("BK"),
                    "bank_date": day.isoformat(),
                    "amount_cents": bank,
                    "ref_type": "GL_ENTRY",
                    "ref_id": je_id,
                }
            )
