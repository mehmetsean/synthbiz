import copy
from datetime import date, timedelta

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from synthbiz.check import run_checks
from synthbiz.dates import business_days, month_ends
from synthbiz.generate import Params, generate


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    months=st.integers(min_value=1, max_value=4),
    rate=st.floats(min_value=0.0, max_value=0.5),
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)),
)
@example(seed=0, months=1, rate=0.0, start=date(2024, 8, 31))
def test_all_rules_pass_for_any_seed(
    seed: int, months: int, rate: float, start: date
) -> None:
    params = Params(seed=seed, months=months, anomaly_rate=rate, start_date=start)
    if not business_days(start, month_ends(start, months)[-1]):
        with pytest.raises(ValueError, match="no business day"):
            generate(params)
        return
    ds = generate(params)
    for r in run_checks(ds.tables, ds.labels):
        assert r.ok, (r.rule, r.messages[:3])
    assert len(ds.labels) == ds.anomaly_count


@settings(max_examples=10, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=1000),
    size=st.sampled_from(["medium", "large"]),
)
def test_bigger_sizes_pass(seed: int, size: str) -> None:
    ds = generate(Params(seed=seed, months=1, size=size, anomaly_rate=0.05))
    assert all(r.ok for r in run_checks(ds.tables, ds.labels))


GOOD = generate(Params(seed=5, months=3, anomaly_rate=0.0))


def _bump(row: dict[str, object], col: str) -> None:
    row[col] = int(str(row[col])) + 1


def _tamper(t: dict[str, list[dict[str, object]]], kind: str, i: int) -> str:
    """Break one cell and return the rule that must catch it."""
    if kind == "journal_amount":
        row = t["journal_lines"][i % len(t["journal_lines"])]
        _bump(row, "debit_cents" if int(str(row["debit_cents"])) else "credit_cents")
        return "balanced_entries"
    if kind == "ap_amount":
        _bump(t["ap_invoices"][i % len(t["ap_invoices"])], "amount_cents")
        return "ap_ar_subledger_ties"
    if kind == "ar_amount":
        _bump(t["ar_invoices"][i % len(t["ar_invoices"])], "amount_cents")
        return "ap_ar_subledger_ties"
    if kind == "bank_amount":
        _bump(t["bank_transactions"][i % len(t["bank_transactions"])], "amount_cents")
        return "bank_ties_to_gl_cash"
    if kind == "vendor_key":
        t["ap_payments"][i % len(t["ap_payments"])]["vendor_id"] = "V-9999"
        return "links"
    if kind == "account_key":
        t["journal_lines"][i % len(t["journal_lines"])]["account_id"] = "9999"
        return "links"
    if kind == "due_date":
        row = t["ar_invoices"][i % len(t["ar_invoices"])]
        d = date.fromisoformat(str(row["invoice_date"])) - timedelta(days=1)
        row["due_date"] = d.isoformat()
        return "dates"
    row = t["journal_lines"][i % len(t["journal_lines"])]
    row["period"] = "1999-01"
    return "dates"


@settings(max_examples=40, deadline=None)
@given(
    kind=st.sampled_from(
        [
            "journal_amount",
            "ap_amount",
            "ar_amount",
            "bank_amount",
            "vendor_key",
            "account_key",
            "due_date",
            "period",
        ]
    ),
    i=st.integers(min_value=0, max_value=10_000),
)
def test_one_broken_cell_fails_its_rule(kind: str, i: int) -> None:
    t = copy.deepcopy(GOOD.tables)
    rule = _tamper(t, kind, i)
    results = {r.rule: r.ok for r in run_checks(t, [])}
    assert results[rule] is False
