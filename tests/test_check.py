import copy
from typing import Any

from synthbiz.check import (
    check_balanced,
    check_bank_tie,
    check_dates,
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
    results = run_checks(good(), [])
    assert [r.rule for r in results] == [
        "balanced_entries",
        "ap_ar_subledger_ties",
        "bank_ties_to_gl_cash",
        "links",
        "dates",
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
    results = run_checks(t, [])
    assert not results[0].ok


def test_links_catch_every_missing_key() -> None:
    t = good()
    t["ap_invoices"][0]["vendor_id"] = "V-9999"
    t["ap_payments"][0]["invoice_id"] = "API-999999"
    t["ar_receipts"][0]["customer_id"] = "C-9999"
    t["journal_lines"][0]["account_id"] = "3100"
    errs = check_links(t)
    assert len(errs) == 4
    assert any("V-9999 not in vendors" in e for e in errs)
    assert any("3100 not in chart_of_accounts" in e for e in errs)


def test_labels_must_point_to_rows() -> None:
    t = good()
    labels = [
        {"table": "ap_payments", "row_id": "APP-999999", "anomaly_type": "x"},
        {"table": "nope", "row_id": "1", "anomaly_type": "x"},
    ]
    errs = check_links(t, labels)
    assert errs == [
        "labels: ap_payments APP-999999 not found",
        "labels: unknown table nope",
    ]


def test_due_date_before_invoice_date_fails() -> None:
    t = good()
    t["ap_invoices"][0]["due_date"] = "2000-01-01"
    errs = check_dates(t, [])
    assert len(errs) == 1
    assert "due date 2000-01-01" in errs[0]


def test_payment_before_invoice_fails() -> None:
    t = good()
    t["ar_receipts"][0]["receipt_date"] = "2000-01-01"
    errs = check_dates(t, [])
    assert len(errs) == 1
    assert "before invoice date" in errs[0]


def test_period_must_match_unless_labeled() -> None:
    t = good()
    line = next(r for r in t["journal_lines"] if r["source_type"] == "MANUAL")
    for r in t["journal_lines"]:
        if r["je_id"] == line["je_id"]:
            r["period"] = "1999-01"
    assert len(check_dates(t, [])) == 2
    label = {
        "table": "journal_lines",
        "row_id": line["line_id"],
        "anomaly_type": "out_of_period_entry",
    }
    assert check_dates(t, [label]) == []


def test_messages_escape_data_values() -> None:
    evil = "\x1b]0;x\x07"
    ds = generate(Params(seed=3, months=2, size="small", anomaly_rate=0))
    tables = copy.deepcopy(ds.tables)
    tables["ap_invoices"][0]["vendor_id"] = evil
    labels = [{"table": "vendors", "row_id": evil, "anomaly_type": "x", "details": ""}]
    errors = check_links(tables, labels)
    assert len(errors) == 2
    for line in errors:
        assert "\x1b" not in line
        assert "\x07" not in line
        assert "\\x1b" in line


def _line(date_text: str, period: str) -> Tables:
    row = {
        "line_id": "JL-1",
        "je_id": "JE-1",
        "posting_date": date_text,
        "period": period,
    }
    return {"journal_lines": [row], "ap_invoices": [], "ar_invoices": []} | {
        "ap_payments": [],
        "ar_receipts": [],
    }


def test_previous_period_allowed_in_close_window() -> None:
    for day, period in [
        ("2025-03-03", "2025-02"),
        ("2025-03-05", "2025-02"),
        ("2025-01-02", "2024-12"),
        ("2025-01-06", "2024-12"),
    ]:
        assert check_dates(_line(day, period), []) == []


def test_previous_period_on_business_day_four_fails() -> None:
    errs = check_dates(_line("2025-03-06", "2025-02"), [])
    assert len(errs) == 1
    assert "not a labeled anomaly" in errs[0]
    label = [
        {
            "table": "journal_lines",
            "row_id": "JL-1",
            "anomaly_type": "out_of_period_entry",
        }
    ]
    assert check_dates(_line("2025-03-06", "2025-02"), label) == []


def test_two_months_back_fails_even_in_close_window() -> None:
    assert check_dates(_line("2025-03-03", "2025-01"), [])
    assert check_dates(_line("2025-03-03", "2025-04"), [])
    assert check_dates(_line("2025-03-03", "2024-12"), [])


def test_extreme_dates_do_not_crash() -> None:
    assert check_dates(_line("9999-12-31", "9999-11"), [])
    assert check_dates(_line("0001-01-02", "0000-12"), [])


def test_bad_posting_date_is_a_finding_not_a_crash() -> None:
    assert check_dates(_line("not-a-date", "2025-02"), [])
