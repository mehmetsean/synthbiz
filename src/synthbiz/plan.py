"""Budget lines and fixed asset, loan and equity entries."""

import random
from typing import Any

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
