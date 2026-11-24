import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.check import run_checks
from synthbiz.cli import main
from synthbiz.dates import business_days, month_ends
from synthbiz.generate import Dataset, Params, generate
from synthbiz.io import read_dataset, verify_manifest, write_dataset
from synthbiz.plan import cash_schedule

Rows = list[dict[str, Any]]


def make(**kw: Any) -> Dataset:
    return generate(Params(budget_and_cash_flow=True, **kw))


def balance(ds: Dataset, role: str, upto: str = "9999-99-99") -> int:
    ids = {a["account_id"] for a in ds.tables["chart_of_accounts"] if a["role"] == role}
    return sum(
        int(r["debit_cents"]) - int(r["credit_cents"])
        for r in ds.tables["journal_lines"]
        if r["account_id"] in ids and r["posting_date"] <= upto
    )


def account_type(ds: Dataset) -> dict[str, str]:
    return {a["account_id"]: a["account_type"] for a in ds.tables["chart_of_accounts"]}


def statement_flows(ds: Dataset) -> dict[str, int]:
    types = account_type(ds)
    roles = {a["account_id"]: a["role"] for a in ds.tables["chart_of_accounts"]}
    out = dict.fromkeys(["net_income", "depreciation", "working_capital"], 0)
    out |= dict.fromkeys(["investing", "financing"], 0)
    for r in ds.tables["journal_lines"]:
        acct = r["account_id"]
        net = int(r["debit_cents"]) - int(r["credit_cents"])
        if types[acct] in ("REVENUE", "EXPENSE"):
            out["net_income"] -= net
            if roles[acct] == "DEPRECIATION":
                out["depreciation"] += net
        elif roles[acct] in ("FIXED_ASSET", "ACCUM_DEPRECIATION"):
            out["investing"] -= net if roles[acct] == "FIXED_ASSET" else 0
        elif types[acct] in ("EQUITY",) or roles[acct] == "LOAN":
            out["financing"] -= net
        elif roles[acct] != "CASH":
            out["working_capital"] -= net
    return out


def direct_flows(ds: Dataset) -> dict[str, int]:
    roles = {a["account_id"]: a["role"] for a in ds.tables["chart_of_accounts"]}
    types = account_type(ds)
    by_je: dict[str, Rows] = {}
    for r in ds.tables["journal_lines"]:
        by_je.setdefault(r["je_id"], []).append(r)
    out = {"operating": 0, "investing": 0, "financing": 0}
    for lines in by_je.values():
        cash = sum(
            int(r["debit_cents"]) - int(r["credit_cents"])
            for r in lines
            if roles[r["account_id"]] == "CASH"
        )
        if cash == 0:
            continue
        other = {r["account_id"] for r in lines if roles[r["account_id"]] != "CASH"}
        if any(roles[a] == "FIXED_ASSET" for a in other):
            out["investing"] += cash
        elif any(roles[a] == "LOAN" or types[a] == "EQUITY" for a in other):
            out["financing"] += cash
        else:
            out["operating"] += cash
    return out


def assert_cash_flow_identity(ds: Dataset) -> None:
    change = balance(ds, "CASH")
    f = statement_flows(ds)
    operating = f["net_income"] + f["depreciation"] + f["working_capital"]
    assert operating + f["investing"] + f["financing"] == change
    d = direct_flows(ds)
    assert d["operating"] + d["investing"] + d["financing"] == change
    assert d["investing"] == f["investing"]
    assert d["financing"] == f["financing"]
    assert d["operating"] == operating


def test_default_run_has_no_plan_data() -> None:
    ds = generate(Params())
    assert "budget_lines" not in ds.tables
    assert len(ds.tables["chart_of_accounts"]) == 11
    assert len(ds.labels) == ds.anomaly_count


def test_plan_does_not_change_existing_rows() -> None:
    base = generate(Params(seed=9, months=4))
    plan = make(seed=9, months=4)
    for name in ("vendors", "customers", "ap_invoices", "ar_invoices"):
        assert plan.tables[name] == base.tables[name]
    keep = {r["line_id"]: r for r in plan.tables["journal_lines"]}
    assert all(keep[r["line_id"]] == r for r in base.tables["journal_lines"])
    assert plan.labels[: len(base.labels)] == base.labels
    assert plan.anomaly_count == base.anomaly_count


def test_twelve_month_balances_by_hand() -> None:
    ds = make(seed=1, months=12)
    assert balance(ds, "FIXED_ASSET") == 33_000_000
    assert balance(ds, "ACCUM_DEPRECIATION") == -(11 * 400_000 + 5 * 150_000)
    assert balance(ds, "LOAN") == -20_000_000
    assert balance(ds, "EQUITY_CONTRIBUTION") == -5_000_000
    assert balance(ds, "DEPRECIATION") == 11 * 400_000 + 5 * 150_000


def test_cash_flow_identity_on_default_seed() -> None:
    ds = make(seed=42, months=12)
    f = statement_flows(ds)
    assert f["investing"] == -33_000_000
    assert f["financing"] == 100_000_000 + 30_000_000 - 10_000_000 + 5_000_000
    assert_cash_flow_identity(ds)


@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=5000),
    months=st.integers(min_value=1, max_value=8),
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2026, 12, 31)),
)
def test_properties_across_seeds(seed: int, months: int, start: date) -> None:
    if not business_days(start, month_ends(start, months)[-1]):
        return
    ds = make(seed=seed, months=months, start_date=start)
    for r in run_checks(ds.tables, ds.labels):
        assert r.ok, (r.rule, r.messages[:3])
    assert_cash_flow_identity(ds)
    sums: dict[str, int] = {}
    for r in ds.tables["journal_lines"]:
        sums[r["je_id"]] = (
            sums.get(r["je_id"], 0) + r["debit_cents"] - r["credit_cents"]
        )
    assert set(sums.values()) == {0}
    planned = [e for e in cash_schedule(months) if e[1] == "DEPRECIATION"]
    posted = [
        r for r in ds.tables["journal_lines"] if r["memo"] == "Monthly depreciation"
    ]
    assert len(posted) == 2 * len(planned)


def test_each_cash_entry_has_a_same_day_bank_line() -> None:
    ds = make(seed=3, months=6)
    jes = {r["je_id"]: r for r in ds.tables["journal_lines"]}
    banks = [b for b in ds.tables["bank_transactions"] if b["ref_type"] == "GL_ENTRY"]
    assert len(banks) == 1 + 1 + 1 + 4
    for b in banks:
        assert b["bank_date"] == jes[b["ref_id"]]["posting_date"]
    dep = {
        r["je_id"]
        for r in ds.tables["journal_lines"]
        if r["memo"].endswith("depreciation")
    }
    assert dep.isdisjoint({b["ref_id"] for b in banks})


def delta_of(details: str) -> int:
    found = re.search(r"delta_cents=(-?[0-9]+)$", details)
    assert found is not None
    return int(found.group(1))


def test_budget_labels_derive_from_data() -> None:
    ds = make(seed=11, months=12, size="medium")
    assert len(ds.tables["budget_lines"]) > 0
    types = account_type(ds)
    actual: dict[tuple[str, str], int] = {}
    for r in ds.tables["journal_lines"]:
        if types[r["account_id"]] in ("REVENUE", "EXPENSE"):
            sign = -1 if types[r["account_id"]] == "REVENUE" else 1
            key = (r["period"], r["account_id"])
            net = r["debit_cents"] - r["credit_cents"]
            actual[key] = actual.get(key, 0) + sign * net
    labeled = {
        lab["row_id"]: delta_of(lab["details"])
        for lab in ds.labels
        if lab["table"] == "budget_lines"
    }
    assert len(labeled) >= 1
    off = 0
    for r in ds.tables["budget_lines"]:
        gap = r["amount_cents"] - actual.get((r["period"], r["account_id"]), 0)
        assert gap == labeled.get(r["budget_id"], 0)
        off += gap != 0
    assert off == len(labeled)


def test_depreciation_is_a_budget_line() -> None:
    ds = make(seed=1, months=3)
    accounts = {r["account_id"] for r in ds.tables["budget_lines"]}
    assert "6500" in accounts


def test_one_month_edge() -> None:
    ds = make(seed=2, months=1)
    assert_cash_flow_identity(ds)
    assert balance(ds, "LOAN") == 0
    assert len(ds.tables["budget_lines"]) == 7


def test_write_read_check_round_trip(tmp_path: Path) -> None:
    ds = make(seed=42, months=6)
    write_dataset(ds, tmp_path)
    tables, labels = read_dataset(tmp_path)
    assert tables["budget_lines"] == [
        {k: str(v) for k, v in r.items()} for r in ds.tables["budget_lines"]
    ]
    assert verify_manifest(tmp_path) == []
    results = run_checks(tables, labels)
    assert "budget_ties_to_journal" in [r.rule for r in results]
    assert all(r.ok for r in results)
    assert "budget_lines" in (tmp_path / "data_dictionary.md").read_text("utf-8")


def test_default_write_has_no_budget_file(tmp_path: Path) -> None:
    write_dataset(generate(Params(months=2)), tmp_path)
    assert not (tmp_path / "budget_lines.csv").exists()
    assert "budget_lines" not in (tmp_path / "schema.json").read_text("utf-8")
    assert "GL_ENTRY" not in (tmp_path / "schema.json").read_text("utf-8")


def test_parquet_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = make(seed=4, months=3)
    write_dataset(ds, tmp_path, "parquet")
    tables, labels = read_dataset(tmp_path)
    assert len(tables["budget_lines"]) == len(ds.tables["budget_lines"])
    assert all(r.ok for r in run_checks(tables, labels))


def test_cli_generate_and_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "d"
    code = main(
        ["generate", "--months", "4", "--budget-and-cash-flow", "--out", str(out)]
    )
    text = capsys.readouterr().out
    assert code == 0
    assert re.search(r"Planted [1-9][0-9]* budget variances", text)
    assert main(["check", str(out)]) == 0
    assert "PASS budget_ties_to_journal" in capsys.readouterr().out


def test_manifest_records_the_option(tmp_path: Path) -> None:
    import json

    ds = make(seed=1, months=4)
    write_dataset(ds, tmp_path)
    m = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    n = sum(1 for lab in ds.labels if lab["table"] == "budget_lines")
    assert m["parameters"]["budget_and_cash_flow"] is True
    assert m["budget_variance_count"] == n > 0
    write_dataset(generate(Params(months=4)), tmp_path / "x")
    m2 = json.loads((tmp_path / "x" / "manifest.json").read_text("utf-8"))
    assert "budget_and_cash_flow" not in m2["parameters"]
    assert "budget_variance_count" not in m2


def test_month_without_business_days_moves_the_entry() -> None:
    ds = make(seed=1, months=2, start_date=date(2025, 8, 30))
    first = [r for r in ds.tables["journal_lines"] if r["memo"] == "Equipment purchase"]
    assert {r["posting_date"] for r in first} == {"2025-09-02"}
    assert_cash_flow_identity(ds)
    assert all(r.ok for r in run_checks(ds.tables, ds.labels))
