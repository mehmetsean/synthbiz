from pathlib import Path
from typing import Any

import pytest

import synthbiz.io
from synthbiz.cli import main
from synthbiz.generate import Params, generate
from synthbiz.io import (
    MAX_ROWS_PER_FILE,
    MAX_TOTAL_ROWS,
    _read_csv,
    _read_parquet,
    read_dataset,
    write_dataset,
)
from synthbiz.schema import columns

BAD_INTS = [" 5", "5 ", "1_000", "+5", "٥", "1" * 19, "1.5", ""]
GOOD_INTS = ["-123", "0", "9" * 18]


def _folder(tmp_path: Path, fmt: str = "csv") -> Path:
    write_dataset(generate(Params(seed=1, months=2)), tmp_path, fmt=fmt)
    (tmp_path / "manifest.json").unlink()
    return tmp_path


def _edit_csv(path: Path, column: str, value: str) -> None:
    lines = path.read_text().splitlines()
    index = lines[0].split(",").index(column)
    cells = lines[1].split(",")
    cells[index] = value
    lines[1] = ",".join(cells)
    path.write_text("\n".join(lines) + "\n")


def _set_parquet(path: Path, column: str, values: list[Any]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    index = table.column_names.index(column)
    values = values + [values[0]] * (table.num_rows - len(values))
    table = table.set_column(index, column, pa.array(values))
    pq.write_table(table, path)


@pytest.mark.parametrize("bad", BAD_INTS)
def test_csv_refuses_other_integer_forms(tmp_path: Path, bad: str) -> None:
    _folder(tmp_path)
    _edit_csv(tmp_path / "bank_transactions.csv", "amount_cents", bad)
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == (
        "bank_transactions.csv: line 2: amount_cents is not a valid integer"
    )


@pytest.mark.parametrize("good", GOOD_INTS)
def test_csv_accepts_plain_integers(tmp_path: Path, good: str) -> None:
    _folder(tmp_path)
    _edit_csv(tmp_path / "bank_transactions.csv", "amount_cents", good)
    tables, _ = read_dataset(tmp_path)
    assert tables["bank_transactions"][0]["amount_cents"] == good


@pytest.mark.parametrize("bad", BAD_INTS[:-2] + ["abc"])
def test_parquet_refuses_other_integer_forms(tmp_path: Path, bad: str) -> None:
    pytest.importorskip("pyarrow")
    _folder(tmp_path, "parquet")
    _set_parquet(tmp_path / "bank_transactions.parquet", "amount_cents", [bad])
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == (
        "bank_transactions.parquet: row 1: amount_cents is not a valid integer"
    )


@pytest.mark.parametrize("good", [-123, 0, 10**18 - 1])
def test_parquet_accepts_plain_integers(tmp_path: Path, good: int) -> None:
    pytest.importorskip("pyarrow")
    _folder(tmp_path, "parquet")
    _set_parquet(tmp_path / "bank_transactions.parquet", "amount_cents", [good])
    tables, _ = read_dataset(tmp_path)
    assert tables["bank_transactions"][0]["amount_cents"] == str(good)


def test_csv_over_cap_stops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _folder(tmp_path)
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", 5)
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value).endswith(".csv: more than 5 rows")


def test_csv_at_cap_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _folder(tmp_path)
    biggest = max(
        len((tmp_path / f"{n}.csv").read_text().splitlines()) - 1
        for n in ("journal_lines", "bank_transactions", "ap_invoices")
    )
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", biggest)
    read_dataset(tmp_path)


def test_parquet_over_cap_is_refused_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    _folder(tmp_path, "parquet")
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", 5)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("data was read")

    monkeypatch.setattr(pq, "read_table", fail)
    monkeypatch.setattr(pq.ParquetFile, "read", fail)
    monkeypatch.setattr(pq.ParquetFile, "iter_batches", fail)
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value).endswith(".parquet: more than 5 rows")


def test_cli_over_cap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _folder(tmp_path)
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", 5)
    assert main(["check", str(tmp_path)]) == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert len(text.splitlines()) == 1
    assert text.startswith("Error: ") and text.endswith("more than 5 rows\n")
    assert "Traceback" not in text


def test_cli_bad_integer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _folder(tmp_path)
    _edit_csv(tmp_path / "journal_lines.csv", "debit_cents", "1_000")
    assert main(["check", str(tmp_path)]) == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert (
        text == "Error: journal_lines.csv: line 2: debit_cents is not a valid integer\n"
    )
    assert "Traceback" not in text


def test_cap_is_above_the_measured_largest_table() -> None:
    # ADR 0013
    assert MAX_ROWS_PER_FILE >= 2 * 1_426_918


COA_ROWS = 11
COA_TYPES = {c: "string" for c in columns("chart_of_accounts")}


def _coa(tmp_path: Path, fmt: str) -> Path:
    _folder(tmp_path, fmt)
    return tmp_path / f"chart_of_accounts.{fmt}"


def _read_one(path: Path) -> list[dict[str, Any]]:
    cols = columns("chart_of_accounts")
    if path.suffix == ".csv":
        return _read_csv(path, cols, COA_TYPES)
    return _read_parquet(path, cols, COA_TYPES)


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_exactly_the_cap_is_read_and_one_more_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    if fmt == "parquet":
        pytest.importorskip("pyarrow")
    path = _coa(tmp_path, fmt)
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", COA_ROWS)
    assert len(_read_one(path)) == COA_ROWS
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", COA_ROWS - 1)
    with pytest.raises(ValueError, match=f"more than {COA_ROWS - 1} rows"):
        _read_one(path)


def test_csv_trailing_blank_lines_do_not_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _coa(tmp_path, "csv")
    with path.open("a") as f:
        f.write("\n\n")
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", COA_ROWS)
    assert len(_read_one(path)) == COA_ROWS


def _folder_rows(folder: Path) -> int:
    tables, labels = read_dataset(folder)
    return sum(len(t) for t in tables.values()) + len(labels)


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_total_cap_over_all_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    if fmt == "parquet":
        pytest.importorskip("pyarrow")
    _folder(tmp_path, fmt)
    total = _folder_rows(tmp_path)
    monkeypatch.setattr(synthbiz.io, "MAX_TOTAL_ROWS", total)
    assert _folder_rows(tmp_path) == total
    monkeypatch.setattr(synthbiz.io, "MAX_TOTAL_ROWS", total - 1)
    with pytest.raises(ValueError, match=f"folder has more than {total - 1} rows"):
        read_dataset(tmp_path)


def test_total_cap_is_above_the_measured_total() -> None:
    # ADR 0013
    assert MAX_TOTAL_ROWS > 1.9 * 2_503_407


def test_parquet_row_groups_are_summed_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    path = _coa(tmp_path, "parquet")
    pq.write_table(pq.read_table(path), path, row_group_size=2)
    real = pq.ParquetFile(path)
    assert real.metadata.num_row_groups > 1

    class Meta:
        num_rows = 0
        num_row_groups = real.metadata.num_row_groups

        def row_group(self, i: int) -> Any:
            return real.metadata.row_group(i)

    class Stub:
        metadata = Meta()

        def __init__(self, _path: Path) -> None:
            pass

        def read(self) -> None:
            raise AssertionError("data was read")

    monkeypatch.setattr(pq, "ParquetFile", Stub)
    monkeypatch.setattr(synthbiz.io, "MAX_ROWS_PER_FILE", COA_ROWS - 1)
    with pytest.raises(ValueError, match="more than 10 rows"):
        _read_one(path)
