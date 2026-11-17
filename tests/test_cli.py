import csv
import runpy
import sys
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
    assert "Error: folder not found" in capsys.readouterr().out


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


def test_no_business_day_reports_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["generate", "--start-date", "2028-12-31", "--months", "1"]
        + ["--out", str(tmp_path / "x")]
    )
    assert code == 1
    assert "Error: no business day" in capsys.readouterr().out


def test_out_folder_must_be_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "stray.txt").write_text("keep me")
    assert gen(tmp_path) == 1
    assert "--force" in capsys.readouterr().out
    assert gen(tmp_path, "--force") == 0
    assert (tmp_path / "stray.txt").read_text() == "keep me"
    assert "stray.txt" not in (tmp_path / "manifest.json").read_text()
    assert main(["check", str(tmp_path)]) == 0


def test_force_switch_format_leaves_one_set(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    assert gen(tmp_path) == 0
    assert gen(tmp_path, "--format", "parquet", "--force") == 0
    assert [f.name for f in tmp_path.glob("*.csv")] == ["labels.csv"]
    assert main(["check", str(tmp_path)]) == 0


def test_check_fails_when_file_changed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gen(tmp_path)
    path = tmp_path / "vendors.csv"
    path.write_text(path.read_text().replace("Co", "Company", 1))
    assert main(["check", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL manifest" in out
    assert "vendors.csv: sha256 differs" in out


def test_check_fails_when_labels_row_deleted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gen(tmp_path, "--anomaly-rate", "0.2")
    path = tmp_path / "labels.csv"
    lines = path.read_text().splitlines(keepends=True)
    path.write_text("".join(lines[:-1]))
    assert main(["check", str(tmp_path)]) == 1
    assert "labels.csv: sha256 differs" in capsys.readouterr().out


def test_check_without_manifest_skips_that_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gen(tmp_path)
    (tmp_path / "manifest.json").unlink()
    assert main(["check", str(tmp_path)]) == 0
    assert "SKIP manifest" in capsys.readouterr().out


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["synthbiz", "--help"])
    with pytest.raises(SystemExit) as e:
        runpy.run_module("synthbiz", run_name="__main__")
    assert e.value.code == 0
