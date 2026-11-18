import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.background import BACKGROUND_KINDS
from synthbiz.builder import APPROVAL_LIMIT_CENTS
from synthbiz.check import run_checks
from synthbiz.cli import main
from synthbiz.dates import (
    business_days,
    is_business_day,
    is_holiday,
    month_ends,
    previous_period,
)
from synthbiz.generate import Dataset, Params, generate

START = date(2025, 1, 1)


def make(background: bool = True, **kw: Any) -> Dataset:
    base: dict[str, Any] = {"seed": 3, "months": 12, "anomaly_rate": 0.0}
    base.update(kw)
    return generate(Params(background=background, **base))


def rows_of(ds: Dataset, kind: str) -> list[dict[str, Any]]:
    table = ds.tables
    out: list[dict[str, Any]] = []
    for x in ds.background:
        if x["kind"] != kind:
            continue
        key = "line_id" if x["table"] == "journal_lines" else "invoice_id"
        found = [r for r in table[x["table"]] if r[key] == x["row_id"]]
        assert len(found) == 1
        out.append(found[0])
    return out


def entry(ds: Dataset, line: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in ds.tables["journal_lines"] if r["je_id"] == line["je_id"]]


def test_default_is_on_and_kinds_are_listed() -> None:
    assert Params().background is True
    assert list(BACKGROUND_KINDS) == sorted(BACKGROUND_KINDS)
    ds = make()
    assert {x["kind"] for x in ds.background} == set(BACKGROUND_KINDS)


def test_off_has_no_background_rows() -> None:
    ds = make(background=False)
    assert ds.background == []
    users = {r["created_by"] for r in ds.tables["journal_lines"]}
    assert not users & {"SYSTEM_BATCH", "SYSTEM_RECURRING", "CFO_1", "TAX_ACCOUNTANT_1"}


def test_checks_pass_and_labels_untouched() -> None:
    ds = make(anomaly_rate=0.1)
    for r in run_checks(ds.tables, ds.labels):
        assert r.ok, (r.rule, r.messages[:3])
    bg_ids = {(x["table"], x["row_id"]) for x in ds.background}
    assert not bg_ids & {(x["table"], x["row_id"]) for x in ds.labels}
    assert len(ds.labels) == ds.anomaly_count


def _journal_key(r: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(sorted(r.items()))


@pytest.mark.parametrize("seed", [1, 2, 42])
def test_background_off_rows_are_a_subset_except_renumbered_ids(seed: int) -> None:
    # renumbered ids
    on = make(seed=seed, anomaly_rate=0.1)
    off = make(background=False, seed=seed, anomaly_rate=0.1)
    assert on.labels == off.labels
    assert on.anomaly_count == off.anomaly_count
    for name in (
        "journal_lines",
        "ap_invoices",
        "ap_payments",
        "ar_invoices",
        "ar_receipts",
        "vendors",
        "customers",
    ):
        have = {_journal_key(r) for r in on.tables[name]}
        assert {_journal_key(r) for r in off.tables[name]} <= have
    keys = ("ref_type", "ref_id", "amount_cents", "bank_date")
    have_bank = {tuple(r[k] for k in keys) for r in on.tables["bank_transactions"]}
    want_bank = {tuple(r[k] for k in keys) for r in off.tables["bank_transactions"]}
    assert want_bank <= have_bank
    assert len(on.tables["journal_lines"]) > len(off.tables["journal_lines"])


def test_system_batch_weekend() -> None:
    ds = make()
    lines = rows_of(ds, "system_batch_weekend")
    assert lines
    days = [date.fromisoformat(r["posting_date"]) for r in lines]
    assert all(d.weekday() >= 5 or is_holiday(d) for d in days)
    assert any(d.weekday() >= 5 for d in days)
    assert any(is_holiday(d) for d in days)
    for r in lines:
        assert r["created_by"] == "SYSTEM_BATCH"
        assert r["approved_by"] == ""
        assert r["memo"] == "Scheduled accrual batch"
        assert r["period"] == r["posting_date"][:7]
        assert r["debit_cents"] % 10_000 != 0
        assert [e["account_id"] for e in entry(ds, r)] == ["6100", "2100"]
    months = Counter(r["posting_date"][:7] for r in lines)
    assert set(months) >= {f"2025-{m:02d}" for m in range(1, 13)}


def test_system_recurring() -> None:
    ds = make()
    lines = rows_of(ds, "system_recurring")
    per_month = Counter(r["period"] for r in lines)
    assert set(per_month.values()) == {2}
    assert len(per_month) == 12
    for r in lines:
        assert is_business_day(date.fromisoformat(r["posting_date"]))
        assert r["created_by"] == "SYSTEM_RECURRING"
        assert r["approved_by"] == ""
        assert r["memo"] == "Recurring accrual"


def test_close_window_accrual() -> None:
    ds = make()
    lines = rows_of(ds, "close_window_accrual")
    assert len(lines) == 11
    assert "2025-01" not in {r["posting_date"][:7] for r in lines}
    for r in lines:
        d = date.fromisoformat(r["posting_date"])
        month_days = [x for x in business_days(date(d.year, d.month, 1), d)]
        assert is_business_day(d)
        assert len(month_days) <= 3
        assert r["period"] == previous_period(d)
        assert r["created_by"] in {"GL_ACCOUNTANT_1", "GL_ACCOUNTANT_2"}
        assert r["approved_by"] == "CONTROLLER_1"
        assert r["memo"] == "Accrual"


def test_close_window_count_scales_with_size() -> None:
    ds = make(size="large", months=3)
    assert len(rows_of(ds, "close_window_accrual")) == 2 * 2


def test_human_weekend_close() -> None:
    ds = make()
    lines = rows_of(ds, "human_weekend_close")
    months = sorted(r["posting_date"][5:7] for r in lines)
    assert months == ["03", "06", "09", "12"]
    for r in lines:
        d = date.fromisoformat(r["posting_date"])
        assert d.weekday() >= 5
        assert (month_ends(d, 1)[0] - d).days < 7
        assert r["period"] == r["posting_date"][:7]
        assert r["created_by"] in {"GL_ACCOUNTANT_1", "GL_ACCOUNTANT_2"}
        assert r["approved_by"] == "CONTROLLER_1"
        assert r["memo"] == "Accrual"


def test_round_rent_accrual() -> None:
    ds = make()
    lines = rows_of(ds, "round_rent_accrual")
    assert len(lines) == 12
    amounts = {r["debit_cents"] for r in lines}
    assert len(amounts) == 1
    amount = amounts.pop()
    assert amount % 100_000 == 0 and 400_000 <= amount <= 1_200_000
    for r in lines:
        d = date.fromisoformat(r["posting_date"])
        assert is_business_day(d)
        assert not business_days(date(d.year, d.month, 1), d)[:-1]
        assert r["account_id"] == "6900"
        assert r["created_by"] == "GL_ACCOUNTANT_1"
        assert r["approved_by"] == "CONTROLLER_1"
        assert r["memo"] == "Rent accrual"


def test_round_retainer_invoice() -> None:
    ds = make()
    invs = rows_of(ds, "round_retainer_invoice")
    assert len(invs) == 12
    assert len({i["vendor_id"] for i in invs}) == 1
    amounts = {i["amount_cents"] for i in invs}
    assert len(amounts) == 1
    assert amounts.pop() in (200_000, 300_000, 400_000)
    vendors = {v["vendor_id"]: v for v in ds.tables["vendors"]}
    assert vendors[invs[0]["vendor_id"]]["category"] == "Services"
    assert [i["invoice_number"] for i in invs] == [
        f"RET-2025{m:02d}" for m in range(1, 13)
    ]
    pays = {p["invoice_id"]: p for p in ds.tables["ap_payments"]}
    paid = [i for i in invs if i["invoice_id"] in pays]
    assert len(paid) >= 9
    for i in paid:
        due = date.fromisoformat(i["due_date"])
        pay = date.fromisoformat(pays[i["invoice_id"]]["payment_date"])
        assert pay >= due and is_business_day(pay)


def test_recurring_fixed_invoice() -> None:
    ds = make()
    invs = rows_of(ds, "recurring_fixed_invoice")
    assert len(invs) >= 50
    assert len({i["vendor_id"] for i in invs}) == 1
    amounts = {i["amount_cents"] for i in invs}
    assert len(amounts) == 1
    assert amounts.pop() % 10_000 != 0
    nums = [int(i["invoice_number"][3:]) for i in invs]
    assert all(i["invoice_number"].startswith("FR-") for i in invs)
    assert nums[0] >= 100
    assert nums == list(range(nums[0], nums[0] + len(nums)))
    weekdays = Counter(date.fromisoformat(i["invoice_date"]).weekday() for i in invs)
    assert len(weekdays) <= 2
    vendors = {v["vendor_id"]: v for v in ds.tables["vendors"]}
    retainer = rows_of(ds, "round_retainer_invoice")[0]["vendor_id"]
    assert invs[0]["vendor_id"] != retainer
    assert vendors[invs[0]["vendor_id"]]


def test_occasional_poster() -> None:
    ds = make()
    lines = rows_of(ds, "occasional_poster")
    cfo = [r for r in lines if r["created_by"] == "CFO_1"]
    tax = [r for r in lines if r["created_by"] == "TAX_ACCOUNTANT_1"]
    assert len(cfo) == 4
    assert len(tax) == 1
    assert len(lines) == 5
    for r in cfo:
        d = date.fromisoformat(r["posting_date"])
        assert is_business_day(d)
        assert (month_ends(d, 1)[0] - d).days < 7
        assert r["approved_by"] == "OWNER_1"
    assert tax[0]["approved_by"] == "CONTROLLER_1"
    assert is_business_day(date.fromisoformat(tax[0]["posting_date"]))


def test_tax_poster_once_per_year() -> None:
    ds = make(months=30)
    tax = [
        r
        for r in rows_of(ds, "occasional_poster")
        if r["created_by"] == "TAX_ACCOUNTANT_1"
    ]
    assert sorted(r["posting_date"][:4] for r in tax) == ["2025", "2026", "2027"]


def test_manifest_fields(tmp_path: Path) -> None:
    for flag, extra in ((True, []), (False, ["--no-background"])):
        out = tmp_path / f"d{flag}"
        code = main(["generate", "--months", "3", "--out", str(out)] + extra)
        assert code == 0
        m = json.loads((out / "manifest.json").read_text())
        assert m["parameters"]["background"] is flag
        assert m["approval_limit_cents"] == APPROVAL_LIMIT_CENTS == 500_000
        counts = m["background_counts"]
        assert list(counts) == sorted(BACKGROUND_KINDS)
        if flag:
            assert all(v > 0 for v in counts.values())
        else:
            assert set(counts.values()) == {0}
        assert main(["check", str(out)]) == 0
        labels = (out / "labels.csv").read_text().splitlines()
        assert len(labels) - 1 == m["anomaly_count"]


def test_manifest_counts_match_dataset(tmp_path: Path) -> None:
    out = tmp_path / "d"
    assert (
        main(
            ["generate", "--months", "4", "--anomaly-rate", "0.1"] + ["--out", str(out)]
        )
        == 0
    )
    m = json.loads((out / "manifest.json").read_text())
    ds = generate(Params(months=4, anomaly_rate=0.1))
    counted = Counter(x["kind"] for x in ds.background)
    assert m["background_counts"] == {k: counted.get(k, 0) for k in BACKGROUND_KINDS}


def test_subledgers_have_no_orphan_bank_rows() -> None:
    ds = make()
    refs = {p["payment_id"] for p in ds.tables["ap_payments"]}
    refs |= {r["receipt_id"] for r in ds.tables["ar_receipts"]}
    refs.add(
        next(
            b["ref_id"]
            for b in ds.tables["bank_transactions"]
            if b["ref_type"] == "OPENING"
        )
    )
    assert {b["ref_id"] for b in ds.tables["bank_transactions"]} == refs


def test_entries_balance_per_je() -> None:
    ds = make(size="medium", months=6)
    sums: dict[str, int] = defaultdict(int)
    for r in ds.tables["journal_lines"]:
        sums[r["je_id"]] += r["debit_cents"] - r["credit_cents"]
    assert set(sums.values()) == {0}


@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=5000),
    months=st.integers(min_value=1, max_value=14),
    size=st.sampled_from(["small", "medium"]),
    rate=st.floats(min_value=0.0, max_value=0.3),
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)),
)
def test_checks_pass_with_background_for_any_seed(
    seed: int, months: int, size: str, rate: float, start: date
) -> None:
    params = Params(
        seed=seed, months=months, size=size, anomaly_rate=rate, start_date=start
    )
    if not business_days(start, month_ends(start, months)[-1]):
        return
    ds = generate(params)
    for r in run_checks(ds.tables, ds.labels):
        assert r.ok, (r.rule, r.messages[:3])
    off = generate(
        Params(
            seed=seed,
            months=months,
            size=size,
            anomaly_rate=rate,
            start_date=start,
            background=False,
        )
    )
    on_lines = {_journal_key(r) for r in ds.tables["journal_lines"]}
    assert {_journal_key(r) for r in off.tables["journal_lines"]} <= on_lines
    assert off.labels == ds.labels
    bg = {x["row_id"] for x in ds.background}
    assert not bg & {x["row_id"] for x in ds.labels}


@settings(max_examples=40, deadline=None)
@given(
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)),
    months=st.integers(min_value=1, max_value=3),
    seed=st.integers(min_value=0, max_value=200),
)
def test_out_of_period_never_in_close_window_any_start(
    start: date, months: int, seed: int
) -> None:
    from synthbiz.dates import in_close_window

    if not business_days(start, month_ends(start, months)[-1]):
        return
    ds = generate(Params(seed=seed, months=months, anomaly_rate=1.0, start_date=start))
    lines = {r["line_id"]: r for r in ds.tables["journal_lines"]}
    for lab in ds.labels:
        if lab["anomaly_type"] == "out_of_period_entry":
            day = date.fromisoformat(lines[lab["row_id"]]["posting_date"])
            assert not in_close_window(day)
