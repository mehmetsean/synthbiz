import copy
from typing import Any

from synthbiz.check import (
    check_balanced,
    check_bank_tie,
    check_links,
    check_subledger_ties,
    month_ends_from_lines,
    reconciling_items,
    run_checks,
)
from synthbiz.generate import Params, generate

Tables = dict[str, list[dict[str, Any]]]


def good() -> Tables:
    ds = generate(Params(seed=3, months=3, size="small", anomaly_rate=0.0))
    return copy.deepcopy(ds.tables)


def test_good_data_passes_every_rule() -> None:
    results = run_checks(good())
    assert [r.rule for r in results] == [
        "balanced_entries",
        "ap_ar_subledger_ties",
        "bank_ties_to_gl_cash",
        "links",
    ]
    assert all(r.ok for r in results), [r.messages for r in results]


def test_unbalanced_entry_fails() -> None:
    t = good()
    t["journal_lines"][5]["debit_cents"] += 1
    errs = check_balanced(t)
    assert len(errs) == 1
    assert t["journal_lines"][5]["je_id"] in errs[0]


def test_ap_tie_fails_when_payment_row_missing() -> None:
    t = good()
    t["ap_payments"].pop(0)
    errs = check_subledger_ties(t)
    assert any(e.startswith("AP") for e in errs)
    assert not any(e.startswith("AR") for e in errs)


def test_ar_tie_fails_when_invoice_amount_changed() -> None:
    t = good()
    t["ar_invoices"][0]["amount_cents"] += 100
    errs = check_subledger_ties(t)
    assert any(e.startswith("AR") for e in errs)


def test_bank_tie_fails_when_bank_amount_changed() -> None:
    t = good()
    t["bank_transactions"][3]["amount_cents"] += 5
    assert check_bank_tie(t)


def test_bank_tie_fails_when_bank_row_dropped() -> None:
    t = good()
    t["bank_transactions"].pop(4)
    assert check_bank_tie(t)


def test_reconciling_table_must_match() -> None:
    t = good()
    assert t["reconciling_items"]
    t["reconciling_items"].pop()
    assert any("reconciling_items" in e for e in check_bank_tie(t))


def test_reconciling_items_explain_the_gap() -> None:
    t = good()
    items = reconciling_items(t, month_ends_from_lines(t["journal_lines"]))
    assert items == t["reconciling_items"]
    kinds = {i["item_type"] for i in items}
    assert kinds <= {"OUTSTANDING_PAYMENT", "DEPOSIT_IN_TRANSIT"}
    for i in items:
        assert i["gl_date"] <= i["month_end"] < i["bank_date"]
        sign = -1 if i["item_type"] == "OUTSTANDING_PAYMENT" else 1
        assert i["amount_cents"] * sign > 0


def test_links_fail_on_missing_entry() -> None:
    t = good()
    t["ap_invoices"][0]["je_id"] = "JE-999999"
    t["bank_transactions"][1]["ref_id"] = "NOPE"
    errs = check_links(t)
    assert len(errs) == 2


def test_run_checks_reports_failures() -> None:
    t = good()
    t["journal_lines"][0]["credit_cents"] += 1
    results = run_checks(t)
    assert not results[0].ok
