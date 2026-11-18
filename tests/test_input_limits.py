from datetime import date
from pathlib import Path
from typing import Any

import pytest

import synthbiz.check
from synthbiz.check import (
    MAX_MONTHS,
    MAX_RECONCILING_ITEMS,
    month_ends_from_lines,
    reconciling_items,
)
from synthbiz.cli import main
from synthbiz.generate import Params, generate
from synthbiz.io import read_dataset, write_dataset
from synthbiz.schema import TABLE_NAMES

BAD_DATES = ["20240131", "2024-W05-3", "2024-1-31", "2024-01-31 "]


def _edit_cell(path: Path, column: str, value: str, line: int = 1) -> None:
    lines = path.read_text().splitlines()
    index = lines[0].split(",").index(column)
    cells = lines[line].split(",")
    cells[index] = value
    lines[line] = ",".join(cells)
    path.write_text("\n".join(lines) + "\n")


def _folder(tmp_path: Path) -> Path:
    ds = generate(Params(seed=1, months=2))
    write_dataset(ds, tmp_path)
    (tmp_path / "manifest.json").unlink()
    return tmp_path


@pytest.mark.parametrize("bad", BAD_DATES)
def test_csv_rejects_other_date_forms(tmp_path: Path, bad: str) -> None:
    _folder(tmp_path)
    _edit_cell(tmp_path / "bank_transactions.csv", "bank_date", bad)
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == (
        "bank_transactions.csv: line 2: bank_date is not a valid date"
    )


def test_parquet_rejects_other_date_forms(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    write_dataset(generate(Params(seed=1, months=2)), tmp_path, fmt="parquet")
    path = tmp_path / "bank_transactions.parquet"
    table = pq.read_table(path)
    index = table.column_names.index("bank_date")
    values = ["20240131"] * table.num_rows
    table = table.set_column(index, "bank_date", pa.array(values))
    pq.write_table(table, path)
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == (
        "bank_transactions.parquet: row 1: bank_date is not a valid date"
    )


def test_cli_bad_date_form(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _folder(tmp_path)
    _edit_cell(tmp_path / "journal_lines.csv", "posting_date", "20240131")
    assert main(["check", str(tmp_path)]) == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert (
        text == "Error: journal_lines.csv: line 2: posting_date is not a valid date\n"
    )
    assert "Traceback" not in text


def test_cli_huge_span(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _folder(tmp_path)
    _edit_cell(tmp_path / "journal_lines.csv", "posting_date", "0001-01-31")
    assert main(["check", str(tmp_path)]) == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert len(text.splitlines()) == 1
    assert text.startswith("Error: could not run the checks: ValueError journal_lines")
    assert f"at most {MAX_MONTHS}" in text
    assert "Traceback" not in text


def test_cli_generate_too_many_months(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["generate", "--months", str(MAX_MONTHS + 1), "--out", str(tmp_path)])
    assert code == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert text == f"Error: months must be at most {MAX_MONTHS}\n"


def _line(day: str) -> dict[str, Any]:
    return {"posting_date": day}


def test_span_limit_is_exact() -> None:
    ok = [_line("2025-01-15"), _line("2025-01-31")]
    assert len(month_ends_from_lines(ok)) == 1
    edge = [_line("2000-01-01"), _line("2099-12-31")]
    assert len(month_ends_from_lines(edge)) == MAX_MONTHS
    over = [_line("2000-01-01"), _line("2100-01-01")]
    with pytest.raises(ValueError, match="span 1201 months; check handles at most"):
        month_ends_from_lines(over)


def _crafted() -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {n: [] for n in TABLE_NAMES}
    tables["ap_payments"] = [{"payment_id": "P1", "payment_date": "2025-01-10"}]
    tables["bank_transactions"] = [
        {
            "bank_txn_id": f"B{i}",
            "bank_date": "2025-06-01",
            "amount_cents": -100,
            "ref_type": "AP_PAYMENT",
            "ref_id": "P1",
        }
        for i in range(3)
    ]
    return tables


ENDS = [date(2025, m, 28) for m in range(1, 7)]


def test_item_limit_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    tables = _crafted()
    assert len(reconciling_items(tables, ENDS)) == 15
    monkeypatch.setattr(synthbiz.check, "MAX_RECONCILING_ITEMS", 14)
    with pytest.raises(ValueError, match="more than 14 reconciling items"):
        reconciling_items(tables, ENDS)
    monkeypatch.setattr(synthbiz.check, "MAX_RECONCILING_ITEMS", 15)
    assert len(reconciling_items(tables, ENDS)) == 15


def test_cli_item_limit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _folder(tmp_path)
    monkeypatch.setattr(synthbiz.check, "MAX_RECONCILING_ITEMS", 1)
    assert main(["check", str(tmp_path)]) == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert len(text.splitlines()) == 1
    assert "reconciling items" in text
    assert "Traceback" not in text


def test_generated_data_stays_far_below_item_limit() -> None:
    ds = generate(Params(seed=42, months=36, size="large"))
    assert len(ds.tables["reconciling_items"]) < MAX_RECONCILING_ITEMS // 100
