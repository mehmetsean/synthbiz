from collections import Counter
from datetime import date
from typing import Any

from synthbiz.anomalies import ANOMALY_TYPES
from synthbiz.builder import APPROVAL_LIMIT_CENTS
from synthbiz.check import run_checks
from synthbiz.dates import is_holiday
from synthbiz.generate import SIZES, Dataset, Params, generate

KEYS = {
    "journal_lines": "line_id",
    "ap_invoices": "invoice_id",
    "ap_payments": "payment_id",
}


def make(
    rate: float = 0.3, months: int = 12, start: date = date(2025, 1, 1)
) -> Dataset:
    return generate(Params(seed=5, months=months, anomaly_rate=rate, start_date=start))


def by_type(ds: Dataset, kind: str) -> list[dict[str, str]]:
    return [x for x in ds.labels if x["anomaly_type"] == kind]


def row(ds: Dataset, label: dict[str, str]) -> dict[str, Any]:
    key = KEYS[label["table"]]
    found = [r for r in ds.tables[label["table"]] if r[key] == label["row_id"]]
    assert len(found) == 1
    return found[0]


def test_label_count_matches_injected_count() -> None:
    ds = make()
    size = SIZES["small"]
    base = 12 * (size.ap_per_month + size.ar_per_month + size.manual_per_month)
    assert ds.anomaly_count == round(0.3 * base)
    assert len(ds.labels) == ds.anomaly_count > 0


def test_labels_point_to_real_rows() -> None:
    ds = make()
    for lab in ds.labels:
        assert lab["table"] in KEYS
        row(ds, lab)
        assert lab["details"]


def test_every_type_appears() -> None:
    ds = make()
    counts = Counter(x["anomaly_type"] for x in ds.labels)
    assert set(counts) == set(ANOMALY_TYPES)
    assert max(counts.values()) - min(counts.values()) <= 1


def test_checks_still_pass_with_anomalies() -> None:
    ds = make()
    for r in run_checks(ds.tables, ds.labels):
        assert r.ok, r.messages


def test_exact_duplicate_payment() -> None:
    ds = make()
    for lab in by_type(ds, "exact_duplicate_payment"):
        p = row(ds, lab)
        same = [
            q
            for q in ds.tables["ap_payments"]
            if q["invoice_id"] == p["invoice_id"]
            and q["amount_cents"] == p["amount_cents"]
            and q["vendor_id"] == p["vendor_id"]
        ]
        assert len(same) == 2


def test_near_duplicate_payment_uses_variant_vendor() -> None:
    ds = make()
    vendors = {v["vendor_id"]: v["vendor_name"] for v in ds.tables["vendors"]}
    invoices = ds.tables["ap_invoices"]
    labels = by_type(ds, "near_duplicate_payment")
    assert labels
    for lab in labels:
        p = row(ds, lab)
        inv = next(i for i in invoices if i["invoice_id"] == p["invoice_id"])
        twins = [
            i
            for i in invoices
            if i["invoice_number"] == inv["invoice_number"]
            and i["amount_cents"] == inv["amount_cents"]
            and i["invoice_id"] != inv["invoice_id"]
        ]
        assert len(twins) == 1
        a, b = vendors[inv["vendor_id"]], vendors[twins[0]["vendor_id"]]
        assert a != b
        assert a.split()[0] == b.split()[0]


def test_split_invoice() -> None:
    ds = make()
    labels = by_type(ds, "split_invoice")
    assert labels
    for lab in labels:
        first = row(ds, lab)
        parts = [
            i
            for i in ds.tables["ap_invoices"]
            if i["vendor_id"] == first["vendor_id"]
            and i["invoice_date"] == first["invoice_date"]
            and APPROVAL_LIMIT_CENTS * 0.9 < i["amount_cents"] < APPROVAL_LIMIT_CENTS
        ]
        assert len(parts) >= 2
        assert sum(p["amount_cents"] for p in parts) > APPROVAL_LIMIT_CENTS


def journal_first(ds: Dataset, lab: dict[str, str]) -> list[dict[str, Any]]:
    line = row(ds, lab)
    return [r for r in ds.tables["journal_lines"] if r["je_id"] == line["je_id"]]


def test_journal_anomalies() -> None:
    ds = make()
    for lab in by_type(ds, "round_amount_entry"):
        assert journal_first(ds, lab)[0]["debit_cents"] % 100_000 == 0
    for lab in by_type(ds, "weekend_posting"):
        d = date.fromisoformat(row(ds, lab)["posting_date"])
        assert d.weekday() >= 5
    for lab in by_type(ds, "holiday_posting"):
        assert is_holiday(date.fromisoformat(row(ds, lab)["posting_date"]))
    for lab in by_type(ds, "unusual_user"):
        assert row(ds, lab)["created_by"] in {"IT_ADMIN_1", "TEMP_USER_1"}
    for lab in by_type(ds, "missing_approval"):
        assert row(ds, lab)["approved_by"] == ""
    for lab in by_type(ds, "out_of_period_entry"):
        r = row(ds, lab)
        assert r["period"] != r["posting_date"][:7]


def test_no_holiday_type_when_range_has_no_holiday() -> None:
    ds = make(rate=0.5, months=1, start=date(2025, 3, 1))
    assert len(ds.labels) == ds.anomaly_count > 0
    assert by_type(ds, "holiday_posting") == []
    for r in run_checks(ds.tables, ds.labels):
        assert r.ok


def test_planted_journal_memos_also_appear_on_normal_rows() -> None:
    ds = generate(Params(seed=42, months=12, anomaly_rate=0.05))
    planted = {x["row_id"] for x in ds.labels if x["table"] == "journal_lines"}
    lines = ds.tables["journal_lines"]
    planted_memos = {r["memo"] for r in lines if r["line_id"] in planted}
    normal_memos = {r["memo"] for r in lines if r["line_id"] not in planted}
    assert planted_memos
    assert planted_memos <= normal_memos


def _distance_ok(a: str, b: str) -> bool:
    if a == b:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return (
            len(diff) == 2
            and diff[1] == diff[0] + 1
            and a[diff[0]] == b[diff[1]]
            and a[diff[1]] == b[diff[0]]
        )
    if abs(len(a) - len(b)) != 1:
        return False
    long, short = (a, b) if len(a) > len(b) else (b, a)
    return any(long[:i] + long[i + 1 :] == short for i in range(len(long)))


def test_typo_duplicate_payment() -> None:
    ds = make()
    labels = by_type(ds, "typo_duplicate_payment")
    assert len(labels) >= 3
    invoices = {i["invoice_id"]: i for i in ds.tables["ap_invoices"]}
    seen = set()
    for lab in labels:
        pay = row(ds, lab)
        twin = invoices[pay["invoice_id"]]
        originals = [
            i
            for i in invoices.values()
            if i["vendor_id"] == twin["vendor_id"]
            and i["amount_cents"] == twin["amount_cents"]
            and i["invoice_date"] == twin["invoice_date"]
            and i["invoice_id"] != twin["invoice_id"]
            and _distance_ok(i["invoice_number"], twin["invoice_number"])
        ]
        assert len(originals) == 1
        assert twin["invoice_number"]
        assert pay["amount_cents"] == twin["amount_cents"]
        paid_first = [
            p
            for p in ds.tables["ap_payments"]
            if p["invoice_id"] == originals[0]["invoice_id"]
        ]
        assert len(paid_first) == 1
        assert paid_first[0]["payment_date"] <= pay["payment_date"]
        assert originals[0]["invoice_number"] in lab["details"]
        assert twin["invoice_number"] in lab["details"]
        assert paid_first[0]["payment_id"] in lab["details"]
        seen.add(lab["row_id"])
    assert len(seen) == len(labels)


def test_typo_duplicate_follows_near_duplicate() -> None:
    i = ANOMALY_TYPES.index("near_duplicate_payment")
    assert ANOMALY_TYPES[i + 1] == "typo_duplicate_payment"
    assert len(ANOMALY_TYPES) == 10


def test_out_of_period_never_in_close_window() -> None:
    from synthbiz.dates import in_close_window

    for seed in range(8):
        ds = generate(Params(seed=seed, months=6, anomaly_rate=0.5))
        labels = by_type(ds, "out_of_period_entry")
        assert labels
        for lab in labels:
            assert not in_close_window(date.fromisoformat(row(ds, lab)["posting_date"]))
