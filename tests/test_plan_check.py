import copy
import re
from pathlib import Path
from typing import Any

import pytest

from synthbiz.check import check_budget, check_links, run_checks
from synthbiz.generate import Params, generate
from synthbiz.io import read_dataset, write_dataset

DS = generate(Params(seed=6, months=3, budget_and_cash_flow=True))


def fresh() -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    return copy.deepcopy(DS.tables), copy.deepcopy(DS.labels)


def planted_row(labels: list[dict[str, Any]]) -> str:
    return next(lab["row_id"] for lab in labels if lab["table"] == "budget_lines")


def test_good_budget_passes() -> None:
    t, labels = fresh()
    assert check_budget(t, labels) == []


def test_changed_amount_fails() -> None:
    t, labels = fresh()
    t["budget_lines"][0]["amount_cents"] += 1
    errs = check_budget(t, labels)
    assert len(errs) == 1
    assert errs[0].startswith("budget_lines BL-000001: amount ")


def test_removed_label_fails() -> None:
    t, labels = fresh()
    gone = planted_row(labels)
    labels = [lab for lab in labels if lab["row_id"] != gone]
    errs = check_budget(t, labels)
    assert len(errs) == 1
    assert errs[0].startswith(f"budget_lines {gone}: amount ")


def test_label_without_delta_fails() -> None:
    t, labels = fresh()
    row = planted_row(labels)
    for lab in labels:
        if lab["row_id"] == row:
            lab["details"] = "budget is higher"
    errs = check_budget(t, labels)
    assert f"labels: {row} has no delta_cents" in errs


def test_duplicate_cell_fails() -> None:
    t, labels = fresh()
    dup = dict(t["budget_lines"][0], budget_id="BL-999999")
    t["budget_lines"].append(dup)
    errs = check_budget(t, labels)
    assert any(e.startswith("budget_lines BL-999999: duplicate cell") for e in errs)


def test_period_without_journal_result_fails() -> None:
    t, labels = fresh()
    t["budget_lines"][0]["period"] = "2031-01"
    errs = check_budget(t, labels)
    assert any(
        e == "budget_lines BL-000001: no journal result for period 2031-01 account 4000"
        for e in errs
    )


def test_unknown_journal_account_is_reported() -> None:
    t, labels = fresh()
    t["journal_lines"][0]["account_id"] = "9999"
    assert check_budget(t, labels) == ["journal line account 9999 is not in the chart"]


def test_label_for_missing_table_is_a_link_error() -> None:
    t, labels = fresh()
    del t["budget_lines"]
    errs = check_links(t, labels)
    assert any("labels: unknown table budget_lines" in e for e in errs)


def test_label_for_missing_budget_row_is_a_link_error() -> None:
    t, labels = fresh()
    labels.append(
        {
            "table": "budget_lines",
            "row_id": "BL-777777",
            "anomaly_type": "budget_variance_pct",
            "details": "x, delta_cents=1",
        }
    )
    assert "labels: budget_lines BL-777777 not found" in check_links(t, labels)


def test_budget_foreign_key_is_checked() -> None:
    t, labels = fresh()
    t["budget_lines"][0]["account_id"] = "8888"
    errs = check_links(t, labels)
    assert "budget_lines BL-000001: account_id 8888 not in chart_of_accounts" in errs


def test_rule_is_absent_without_the_table() -> None:
    plain = generate(Params(seed=6, months=2))
    names = [r.rule for r in run_checks(plain.tables, plain.labels)]
    assert "budget_ties_to_journal" not in names


def test_loader_rejects_bad_budget_columns(tmp_path: Path) -> None:
    write_dataset(DS, tmp_path)
    path = tmp_path / "budget_lines.csv"
    text = path.read_text("utf-8").replace("amount_cents", "amount", 1)
    path.write_text(text, "utf-8")
    want = re.escape("budget_lines.csv: columns do not match the schema")
    with pytest.raises(ValueError, match=want):
        read_dataset(tmp_path)


def test_loader_rejects_bad_budget_amount(tmp_path: Path) -> None:
    write_dataset(DS, tmp_path)
    path = tmp_path / "budget_lines.csv"
    lines = path.read_text("utf-8").split("\n")
    first = lines[1].split(",")
    first[3] = "12.5"
    lines[1] = ",".join(first)
    path.write_text("\n".join(lines), "utf-8")
    want = re.escape("budget_lines.csv: line 2: amount_cents is not a valid integer")
    with pytest.raises(ValueError, match=want):
        read_dataset(tmp_path)


def test_loader_rejects_both_budget_formats(tmp_path: Path) -> None:
    write_dataset(DS, tmp_path)
    (tmp_path / "budget_lines.parquet").write_bytes(b"")
    want = re.escape("both budget_lines.csv and budget_lines.parquet are in")
    with pytest.raises(ValueError, match=want):
        read_dataset(tmp_path)


def test_folder_without_budget_file_still_reads(tmp_path: Path) -> None:
    write_dataset(generate(Params(months=2)), tmp_path)
    tables, _ = read_dataset(tmp_path)
    assert "budget_lines" not in tables


def test_force_replaces_budget_file(tmp_path: Path) -> None:
    write_dataset(DS, tmp_path)
    write_dataset(generate(Params(months=2)), tmp_path, force=True)
    assert not (tmp_path / "budget_lines.csv").exists()
