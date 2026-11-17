import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import synthbiz.io
from synthbiz import __version__
from synthbiz.check import run_checks
from synthbiz.generate import Params, generate
from synthbiz.io import read_dataset, verify_manifest, write_dataset
from synthbiz.schema import TABLE_NAMES, columns

PARAMS = Params(seed=11, months=2, size="small", anomaly_rate=0.1)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_files_written(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    for name in TABLE_NAMES:
        first = (tmp_path / f"{name}.csv").read_text().splitlines()[0]
        assert first.split(",") == columns(name)
    labels = (tmp_path / "labels.csv").read_text().splitlines()
    assert labels[0] == "table,row_id,anomaly_type,details"
    for f in ("schema.json", "data_dictionary.md", "manifest.json", "README.txt"):
        assert (tmp_path / f).exists()


def test_no_comment_lines_in_csv(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    for f in tmp_path.glob("*.csv"):
        assert not f.read_text().startswith("#")


def test_manifest(tmp_path: Path) -> None:
    ds = generate(PARAMS)
    write_dataset(ds, tmp_path)
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["synthetic"] is True
    assert m["synthbiz_version"] == __version__
    assert m["parameters"]["seed"] == 11
    assert m["parameters"]["months"] == 2
    assert m["anomaly_count"] == ds.anomaly_count
    assert "manifest.json" not in m["files"]
    assert "labels.csv" in m["files"]
    for name, digest in m["files"].items():
        assert sha(tmp_path / name) == digest


def test_readme_text(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    text = (tmp_path / "README.txt").read_text()
    assert "synthetic data" in text.lower()
    assert "unintended" in text
    assert (
        "Synthetic data for testing and learning only. Any match with a real "
        "business is unintended. Decision support only, not legal, tax, "
        "accounting or assurance advice. No guarantee of compliance."
    ) in text.splitlines()
    assert "CC BY 4.0" in text


def test_no_long_dashes(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    for f in tmp_path.iterdir():
        text = f.read_text()
        assert chr(0x2013) not in text
        assert chr(0x2014) not in text


def test_deterministic_bytes(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    write_dataset(generate(PARAMS), a)
    write_dataset(generate(PARAMS), b)
    names = sorted(p.name for p in a.iterdir())
    assert names == sorted(p.name for p in b.iterdir())
    for n in names:
        assert sha(a / n) == sha(b / n)


def test_roundtrip_and_check(tmp_path: Path) -> None:
    ds = generate(PARAMS)
    write_dataset(ds, tmp_path)
    tables, labels = read_dataset(tmp_path)
    assert len(labels) == ds.anomaly_count
    assert len(tables["journal_lines"]) == len(ds.tables["journal_lines"])
    assert all(r.ok for r in run_checks(tables, labels))


def test_parquet_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    write_dataset(generate(PARAMS), tmp_path, fmt="parquet")
    assert (tmp_path / "vendors.parquet").exists()
    assert not (tmp_path / "vendors.csv").exists()
    assert (tmp_path / "labels.csv").exists()
    tables, labels = read_dataset(tmp_path)
    assert all(r.ok for r in run_checks(tables, labels))


def test_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_dataset(generate(PARAMS), tmp_path, fmt="xlsx")


def test_read_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_dataset(tmp_path)


def test_golden_checksum_seed_42(tmp_path: Path) -> None:
    ds = generate(Params(seed=42, months=3))
    write_dataset(ds, tmp_path)
    assert sha(tmp_path / "journal_lines.csv") == (
        "5a93b15aa3e28d9158f1e0cadb32667d4ef59b91ab89e718cbe84d71f0a3c18c"
    )
    assert sha(tmp_path / "bank_transactions.csv") == (
        "5058b0f6ae6db056594cf3702181daa53437833a655023cff52e405d0a90dc64"
    )


def test_manifest_lists_only_written_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("mine")
    write_dataset(generate(PARAMS), tmp_path, force=True)
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert "notes.txt" not in m["files"]
    assert verify_manifest(tmp_path) == []


def test_refuses_non_empty_folder(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("mine")
    with pytest.raises(FileExistsError):
        write_dataset(generate(PARAMS), tmp_path)


def test_refuses_a_file_as_out(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(FileExistsError):
        write_dataset(generate(PARAMS), f)


def test_verify_manifest_cases(tmp_path: Path) -> None:
    assert verify_manifest(tmp_path) is None
    write_dataset(generate(PARAMS), tmp_path)
    (tmp_path / "labels.csv").unlink()
    (tmp_path / "vendors.parquet").write_text("x")
    assert verify_manifest(tmp_path) == [
        "labels.csv: listed in manifest.json but missing",
        "vendors.parquet: in the folder but not in manifest.json",
    ]
    (tmp_path / "manifest.json").write_text("[]")
    assert verify_manifest(tmp_path) == ["manifest.json could not be read"]


def test_read_refuses_two_formats(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    (tmp_path / "vendors.parquet").write_text("x")
    with pytest.raises(ValueError, match="both vendors.csv and vendors.parquet"):
        read_dataset(tmp_path)


def test_manifest_names_must_be_known(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    path = tmp_path / "manifest.json"
    m = json.loads(path.read_text())
    m["files"]["../outside.txt"] = "0" * 64
    m["files"][str(tmp_path.parent / "abs.txt")] = "0" * 64
    path.write_text(json.dumps(m))
    errs = verify_manifest(tmp_path)
    assert errs is not None and len(errs) == 2
    assert all(e.startswith("unexpected file name in manifest.json") for e in errs)


def test_deeply_nested_manifest(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    (tmp_path / "manifest.json").write_text("[" * 100_000)
    assert verify_manifest(tmp_path) == ["manifest.json could not be read"]


def test_manifest_name_outside_folder_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "data"
    write_dataset(generate(PARAMS), folder)
    secret = tmp_path / "outside.csv"
    secret.write_text("secret content")
    path = folder / "manifest.json"
    m = json.loads(path.read_text())
    m["files"]["../outside.csv"] = "0" * 64
    path.write_text(json.dumps(m))
    seen: list[str] = []
    real = synthbiz.io._sha256

    def spy(p: Path) -> str:
        seen.append(p.name)
        return real(p)

    monkeypatch.setattr(synthbiz.io, "_sha256", spy)
    errs = verify_manifest(folder)
    assert errs == ["unexpected file name in manifest.json: '../outside.csv'"]
    assert "outside.csv" not in seen
    assert "secret content" not in str(errs)


def _edit(path: Path, fn: Callable[[list[str]], list[str]]) -> None:
    lines = path.read_text().splitlines()
    path.write_text("\n".join(fn(lines)) + "\n")


def test_missing_column_rejected(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    _edit(
        tmp_path / "bank_transactions.csv",
        lambda ls: [line.rsplit(",", 1)[0] for line in ls],
    )
    with pytest.raises(ValueError, match="bank_transactions.csv: columns do not"):
        read_dataset(tmp_path)


def test_extra_column_rejected(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    _edit(tmp_path / "vendors.csv", lambda ls: [line + ",x" for line in ls])
    with pytest.raises(ValueError, match="vendors.csv: columns do not"):
        read_dataset(tmp_path)


def test_short_row_rejected(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    _edit(
        tmp_path / "journal_lines.csv",
        lambda ls: [ls[0], ls[1].split(",")[0], *ls[2:]],
    )
    with pytest.raises(ValueError, match="journal_lines.csv: line 2 has 1 fields"):
        read_dataset(tmp_path)


def test_long_row_rejected(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    _edit(tmp_path / "vendors.csv", lambda ls: [*ls[:2], ls[2] + ",x", *ls[3:]])
    with pytest.raises(ValueError, match="vendors.csv: line 3 has"):
        read_dataset(tmp_path)


def test_bad_labels_rejected(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    _edit(tmp_path / "labels.csv", lambda ls: ["table,row_id", *ls[1:]])
    with pytest.raises(ValueError, match="labels.csv: columns do not"):
        read_dataset(tmp_path)


def test_empty_file_rejected(tmp_path: Path) -> None:
    write_dataset(generate(PARAMS), tmp_path)
    (tmp_path / "vendors.csv").write_text("")
    with pytest.raises(ValueError, match="vendors.csv: file is empty"):
        read_dataset(tmp_path)


def _fresh(tmp_path: Path) -> Path:
    write_dataset(generate(PARAMS), tmp_path)
    return tmp_path


def test_non_numeric_amount_rejected(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "bank_transactions.csv"
    lines = path.read_text().splitlines()
    cells = lines[1].split(",")
    cells[2] = "abc"
    lines[1] = ",".join(cells)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == (
        "bank_transactions.csv: line 2: amount_cents is not a valid integer"
    )


def test_bad_date_rejected(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "bank_transactions.csv"
    lines = path.read_text().splitlines()
    cells = lines[1].split(",")
    cells[1] = "2025-13-45"
    lines[1] = ",".join(cells)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="line 2: bank_date is not a valid date"):
        read_dataset(tmp_path)


def test_huge_field_rejected(tmp_path: Path) -> None:
    _fresh(tmp_path)
    (tmp_path / "vendors.csv").write_text('a,b\n"' + "x" * 200000 + '",1\n')
    with pytest.raises(ValueError, match="vendors.csv: not valid CSV"):
        read_dataset(tmp_path)


def test_not_utf8_rejected(tmp_path: Path) -> None:
    _fresh(tmp_path)
    (tmp_path / "vendors.csv").write_bytes(b"vendor_id\n\xff\xfe\n")
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == "vendors.csv: not valid UTF-8"


def test_bom_accepted(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "vendors.csv"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    tables, _ = read_dataset(tmp_path)
    assert tables["vendors"]


def test_header_is_not_echoed_raw(tmp_path: Path) -> None:
    _fresh(tmp_path)
    (tmp_path / "vendors.csv").write_text("\x1b[31m" + "h" * 5000 + "\n")
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert "\x1b" not in str(e.value)
    assert len(str(e.value)) < 600


def test_reordered_columns_rejected(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "labels.csv"
    _edit(path, lambda ls: ["row_id,table,anomaly_type,details", *ls[1:]])
    with pytest.raises(ValueError, match="labels.csv: columns do not"):
        read_dataset(tmp_path)


def test_blank_middle_line_reports_physical_line(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "vendors.csv"
    _edit(path, lambda ls: [*ls[:3], "", *ls[3:]])
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == "vendors.csv: line 4 is blank"


def test_trailing_blank_lines_are_fine(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "vendors.csv"
    path.write_text(path.read_text() + "\n\n")
    tables, _ = read_dataset(tmp_path)
    assert tables["vendors"]


def test_line_number_counts_physical_lines(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "labels.csv"
    path.write_text('table,row_id,anomaly_type,details\na,b,c,"x\ny\nz"\nshort\n')
    with pytest.raises(ValueError, match="labels.csv: line 5 has 1 fields"):
        read_dataset(tmp_path)


def test_crlf_and_quoted_comma(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "labels.csv"
    path.write_bytes(b'table,row_id,anomaly_type,details\r\na,b,c,"x, y"\r\n')
    _, labels = read_dataset(tmp_path)
    assert labels == [
        {"table": "a", "row_id": "b", "anomaly_type": "c", "details": "x, y"}
    ]


def test_header_only_file(tmp_path: Path) -> None:
    _fresh(tmp_path)
    path = tmp_path / "labels.csv"
    path.write_text("table,row_id,anomaly_type,details\n")
    assert read_dataset(tmp_path)[1] == []


def test_directory_instead_of_file(tmp_path: Path) -> None:
    _fresh(tmp_path)
    (tmp_path / "vendors.csv").unlink()
    (tmp_path / "vendors.csv").mkdir()
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value).startswith("vendors.csv: could not read the file")
    assert str(tmp_path) not in str(e.value)


def test_parquet_without_pyarrow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fresh(tmp_path)
    (tmp_path / "vendors.csv").unlink()
    (tmp_path / "vendors.parquet").write_bytes(b"x")
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", None)
    with pytest.raises(ValueError, match="vendors.parquet: pyarrow is needed"):
        read_dataset(tmp_path)


def test_corrupt_parquet(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    _fresh(tmp_path)
    (tmp_path / "vendors.csv").unlink()
    (tmp_path / "vendors.parquet").write_bytes(b"junk bytes")
    with pytest.raises(ValueError) as e:
        read_dataset(tmp_path)
    assert str(e.value) == "vendors.parquet: not a readable Parquet file"


def test_parquet_column_mismatch(tmp_path: Path) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    pa = pytest.importorskip("pyarrow")
    write_dataset(generate(PARAMS), tmp_path, "parquet")
    pq.write_table(pa.table({"wrong": ["a"]}), tmp_path / "vendors.parquet")
    with pytest.raises(ValueError, match="vendors.parquet: columns do not"):
        read_dataset(tmp_path)
