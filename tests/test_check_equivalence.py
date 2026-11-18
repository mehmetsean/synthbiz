import copy
from datetime import date
from typing import Any

from benchmarks import baseline as ref
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz import check as new
from synthbiz.dates import business_days, month_ends
from synthbiz.generate import Params, generate
from synthbiz.schema import TABLE_NAMES

Tables = dict[str, list[dict[str, Any]]]


def _same_results(tables: Tables, labels: list[dict[str, Any]]) -> None:
    got = new.run_checks(tables, labels)
    want = ref.run_checks(tables, labels)
    assert [(r.rule, r.ok, r.messages) for r in got] == [
        (r.rule, r.ok, r.messages) for r in want
    ]


def _same_items(tables: Tables) -> None:
    ends = new.month_ends_from_lines(tables["journal_lines"])
    assert ends == ref.month_ends_from_lines(tables["journal_lines"])
    assert new.reconciling_items(tables, ends) == ref.reconciling_items(tables, ends)


def _make(seed: int, months: int, rate: float, start: date, size: str) -> Any:
    params = Params(
        seed=seed, months=months, anomaly_rate=rate, start_date=start, size=size
    )
    if not business_days(start, month_ends(start, months)[-1]):
        return None
    return generate(params)


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    months=st.integers(min_value=1, max_value=6),
    rate=st.floats(min_value=0.0, max_value=0.5),
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)),
)
def test_small_matches_reference(
    seed: int, months: int, rate: float, start: date
) -> None:
    ds = _make(seed, months, rate, start, "small")
    if ds is None:
        return
    _same_results(ds.tables, ds.labels)
    _same_items(ds.tables)


@settings(max_examples=6, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=1000),
    size=st.sampled_from(["medium", "large"]),
    months=st.integers(min_value=1, max_value=3),
    rate=st.floats(min_value=0.0, max_value=0.5),
)
def test_bigger_sizes_match_reference(
    seed: int, size: str, months: int, rate: float
) -> None:
    ds = _make(seed, months, rate, date(2025, 1, 1), size)
    _same_results(ds.tables, ds.labels)
    _same_items(ds.tables)


GOOD = generate(Params(seed=7, months=4, anomaly_rate=0.1))
TABLES_WITH_DATES = {
    "journal_lines": "posting_date",
    "ap_invoices": "invoice_date",
    "ap_payments": "payment_date",
    "ar_invoices": "invoice_date",
    "ar_receipts": "receipt_date",
    "bank_transactions": "bank_date",
}
KINDS = ["amount", "date", "delete", "foreign_key", "label"]
EDITABLE = [
    "journal_lines",
    "ap_invoices",
    "ap_payments",
    "ar_invoices",
    "ar_receipts",
    "bank_transactions",
]
FK_COLUMN = {
    "journal_lines": "account_id",
    "ap_invoices": "vendor_id",
    "ap_payments": "invoice_id",
    "ar_invoices": "customer_id",
    "ar_receipts": "invoice_id",
    "bank_transactions": "ref_id",
}
AMOUNT_COLUMN = {
    "journal_lines": "debit_cents",
    "ap_invoices": "amount_cents",
    "ap_payments": "amount_cents",
    "ar_invoices": "amount_cents",
    "ar_receipts": "amount_cents",
    "bank_transactions": "amount_cents",
}

edit = st.tuples(
    st.sampled_from(KINDS),
    st.sampled_from(EDITABLE),
    st.integers(min_value=0, max_value=10_000),
    st.integers(min_value=-5000, max_value=5000),
    st.dates(min_value=date(2023, 6, 1), max_value=date(2028, 6, 30)),
)


def _apply(tables: Tables, labels: list[dict[str, Any]], e: tuple[Any, ...]) -> None:
    kind, name, pick, delta, day = e
    rows = tables[name]
    if kind == "label":
        if labels:
            labels[pick % len(labels)]["row_id"] = f"MISSING-{pick}"
        return
    if not rows:
        return
    row = rows[pick % len(rows)]
    if kind == "amount":
        col = AMOUNT_COLUMN[name]
        row[col] = int(row[col]) + delta
    elif kind == "date":
        row[TABLES_WITH_DATES[name]] = day.isoformat()
    elif kind == "delete":
        del rows[pick % len(rows)]
    else:
        row[FK_COLUMN[name]] = f"MISSING-{pick}"


@settings(max_examples=60, deadline=None)
@given(edits=st.lists(edit, min_size=1, max_size=4))
def test_tampered_data_matches_reference(edits: list[tuple[Any, ...]]) -> None:
    tables = copy.deepcopy(GOOD.tables)
    labels = copy.deepcopy(GOOD.labels)
    for e in edits:
        _apply(tables, labels, e)
    _same_results(tables, labels)
    _same_items(tables)


def _tables(**rows: list[dict[str, Any]]) -> Tables:
    return {n: rows.get(n, []) for n in TABLE_NAMES}


def _payment(pid: str, day: str) -> dict[str, Any]:
    return {"payment_id": pid, "payment_date": day}


def _bank(ref_id: str, day: str, amount: int, ref_type: str) -> dict[str, Any]:
    return {
        "ref_id": ref_id,
        "bank_date": day,
        "amount_cents": amount,
        "ref_type": ref_type,
    }


ENDS = [date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)]


def test_empty_tables() -> None:
    t = _tables()
    assert new.reconciling_items(t, ENDS) == []
    assert new.reconciling_items(t, []) == []
    assert new.month_ends_from_lines([]) == []
    _same_results(t, [])


def test_gl_date_after_bank_date_gives_no_item() -> None:
    t = _tables(
        ap_payments=[_payment("P1", "2025-02-10")],
        bank_transactions=[_bank("P1", "2025-02-05", -100, "AP_PAYMENT")],
    )
    assert new.reconciling_items(t, ENDS) == []
    assert ref.reconciling_items(t, ENDS) == []


def test_bank_date_on_month_end_is_not_in_transit() -> None:
    t = _tables(
        ap_payments=[_payment("P1", "2025-01-20")],
        bank_transactions=[_bank("P1", "2025-01-31", -100, "AP_PAYMENT")],
    )
    assert new.reconciling_items(t, ENDS) == []
    assert ref.reconciling_items(t, ENDS) == []


def test_gl_date_on_month_end_counts_for_that_end() -> None:
    t = _tables(
        ap_payments=[_payment("P1", "2025-01-31")],
        bank_transactions=[_bank("P1", "2025-03-02", -100, "AP_PAYMENT")],
    )
    got = new.reconciling_items(t, ENDS)
    assert [i["month_end"] for i in got] == ["2025-01-31", "2025-02-28"]
    assert got == ref.reconciling_items(t, ENDS)


def test_row_after_last_month_end_counts_nowhere() -> None:
    t = _tables(
        ap_payments=[_payment("P1", "2025-03-31")],
        bank_transactions=[_bank("P1", "2025-04-03", -100, "AP_PAYMENT")],
    )
    got = new.reconciling_items(t, ENDS)
    assert [i["month_end"] for i in got] == ["2025-03-31"]
    assert got == ref.reconciling_items(t, ENDS)
    late = _tables(
        ap_payments=[_payment("P1", "2025-04-01")],
        bank_transactions=[_bank("P1", "2025-04-03", -100, "AP_PAYMENT")],
    )
    assert new.reconciling_items(late, ENDS) == []


def test_wrong_ref_type_is_skipped() -> None:
    t = _tables(
        ap_payments=[_payment("P1", "2025-01-10")],
        bank_transactions=[_bank("P1", "2025-02-05", 100, "AR_RECEIPT")],
    )
    assert new.reconciling_items(t, ENDS) == []


def test_ties_match_reference_on_edge_rows() -> None:
    lines = [
        {
            "line_id": "L1",
            "je_id": "J1",
            "posting_date": d,
            "account_id": "1000",
            "debit_cents": 100,
            "credit_cents": 0,
        }
        for d in ["2025-01-31", "2025-02-01", "2025-03-31"]
    ]
    coa = [{"account_id": "1000", "role": "CASH"}]
    t = _tables(
        chart_of_accounts=coa,
        journal_lines=lines,
        bank_transactions=[
            _bank("X", "2025-01-31", 100, "OPENING"),
            _bank("Y", "2025-04-15", 100, "OPENING"),
        ],
    )
    got = new.check_bank_tie(t)
    assert got == ref.check_bank_tie(t)
    assert got


def test_unknown_table_label_is_reported() -> None:
    labels = [{"table": "nope", "row_id": "1"}]
    t = copy.deepcopy(GOOD.tables)
    assert new.check_links(t, labels) == ref.check_links(t, labels)
