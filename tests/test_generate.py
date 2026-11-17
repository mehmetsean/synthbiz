from collections import defaultdict
from datetime import date

import pytest

from synthbiz.dates import is_business_day
from synthbiz.generate import SIZES, Params, generate
from synthbiz.schema import TABLE_NAMES, columns


def make(**kw: object) -> Params:
    base: dict[str, object] = {
        "seed": 7,
        "months": 3,
        "size": "small",
        "anomaly_rate": 0.0,
    }
    base.update(kw)
    return Params(**base)  # type: ignore[arg-type]


def test_all_tables_and_columns() -> None:
    ds = generate(make())
    for name in TABLE_NAMES:
        assert name in ds.tables
        for row in ds.tables[name]:
            assert list(row) == columns(name)


def test_no_anomalies_means_no_labels() -> None:
    ds = generate(make())
    assert ds.labels == []
    assert ds.anomaly_count == 0


def test_entries_balance_and_amounts_are_integers() -> None:
    ds = generate(make())
    sums: dict[str, int] = defaultdict(int)
    for r in ds.tables["journal_lines"]:
        assert isinstance(r["debit_cents"], int)
        assert isinstance(r["credit_cents"], int)
        assert (r["debit_cents"] == 0) != (r["credit_cents"] == 0)
        sums[r["je_id"]] += r["debit_cents"] - r["credit_cents"]
    assert set(sums.values()) == {0}


def test_subledger_rows_link_to_entries() -> None:
    ds = generate(make())
    jes = {r["je_id"] for r in ds.tables["journal_lines"]}
    for t in ("ap_invoices", "ap_payments", "ar_invoices", "ar_receipts"):
        assert ds.tables[t]
        for r in ds.tables[t]:
            assert r["je_id"] in jes


def test_bank_rows_clear_real_payments_and_receipts() -> None:
    ds = generate(make())
    pays = {r["payment_id"]: r for r in ds.tables["ap_payments"]}
    recs = {r["receipt_id"]: r for r in ds.tables["ar_receipts"]}
    seen = set()
    for b in ds.tables["bank_transactions"]:
        if b["ref_type"] == "AP_PAYMENT":
            p = pays[b["ref_id"]]
            assert b["amount_cents"] == -p["amount_cents"]
            assert b["bank_date"] > p["payment_date"]
        elif b["ref_type"] == "AR_RECEIPT":
            r = recs[b["ref_id"]]
            assert b["amount_cents"] == r["amount_cents"]
            assert b["bank_date"] > r["receipt_date"]
        else:
            assert b["ref_type"] == "OPENING"
        seen.add(b["ref_id"])
    assert set(pays) <= seen
    assert set(recs) <= seen


def test_normal_postings_on_business_days() -> None:
    ds = generate(make())
    for r in ds.tables["journal_lines"]:
        assert is_business_day(date.fromisoformat(r["posting_date"]))
        assert r["period"] == r["posting_date"][:7]
        assert r["approved_by"] != ""


def test_dates_inside_range() -> None:
    ds = generate(make(start_date=date(2025, 1, 1), months=2))
    dates = [r["posting_date"] for r in ds.tables["journal_lines"]]
    assert min(dates) >= "2025-01-01"
    assert max(dates) <= "2025-02-28"


def test_no_person_names_in_users() -> None:
    ds = generate(make(anomaly_rate=0.2))
    users = {r["created_by"] for r in ds.tables["journal_lines"]}
    users |= {r["approved_by"] for r in ds.tables["journal_lines"]}
    for u in users:
        assert u == "" or u.replace("_", "").isalnum() and u.upper() == u


def test_sizes_scale() -> None:
    small = generate(make(size="small", months=1))
    medium = generate(make(size="medium", months=1))
    assert len(medium.tables["ap_invoices"]) > len(small.tables["ap_invoices"])
    assert len(medium.tables["vendors"]) == SIZES["medium"].vendors


def test_unknown_size_rejected() -> None:
    with pytest.raises(ValueError):
        generate(make(size="huge"))


def test_months_must_be_positive() -> None:
    with pytest.raises(ValueError):
        generate(make(months=0))


def test_same_seed_same_data_different_seed_differs() -> None:
    a = generate(make())
    b = generate(make())
    c = generate(make(seed=8))
    assert a.tables == b.tables
    assert a.tables != c.tables
