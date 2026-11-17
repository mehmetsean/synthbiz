import csv
from pathlib import Path

import pytest

from synthbiz.cli import main


def gen(out: Path, *extra: str) -> int:
    return main(["generate", "--seed", "1", "--months", "2", "--out", str(out), *extra])


def test_generate_then_check_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gen(tmp_path) == 0
    assert (tmp_path / "manifest.json").exists()
    assert main(["check", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "PASS balanced_entries" in out
    assert "All checks passed" in out


def test_check_fails_on_broken_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gen(tmp_path, "--anomaly-rate", "0")
    path = tmp_path / "journal_lines.csv"
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    rows[3][6] = str(int(rows[3][6]) + 1)
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    assert main(["check", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL balanced_entries" in out
    assert "Some checks failed" in out


def test_check_missing_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(tmp_path / "nope")]) == 1
    assert "error" in capsys.readouterr().out.lower()


def test_options(tmp_path: Path) -> None:
    code = main(
        [
            "generate", "--seed", "3", "--months", "1", "--size", "medium",
            "--anomaly-rate", "0.05", "--start-date", "2026-02-01",
            "--out", str(tmp_path),
        ]
    )  # fmt: skip
    assert code == 0
    assert '"start_date": "2026-02-01"' in (tmp_path / "manifest.json").read_text()


def test_parquet_option(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    assert gen(tmp_path, "--format", "parquet") == 0
    assert main(["check", str(tmp_path)]) == 0


def test_bad_size_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        gen(tmp_path, "--size", "huge")


def test_no_command_exits() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_bad_months_reports_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["generate", "--months", "0", "--out", str(tmp_path)]) == 1
    assert "Error" in capsys.readouterr().out
