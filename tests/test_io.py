import hashlib
import json
from pathlib import Path

import pytest

from synthbiz import __version__
from synthbiz.check import run_checks
from synthbiz.generate import Params, generate
from synthbiz.io import read_dataset, write_dataset
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
    assert "not accounting, tax or assurance advice" in text


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
    assert all(r.ok for r in run_checks(tables))


def test_parquet_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    write_dataset(generate(PARAMS), tmp_path, fmt="parquet")
    assert (tmp_path / "vendors.parquet").exists()
    assert not (tmp_path / "vendors.csv").exists()
    assert (tmp_path / "labels.csv").exists()
    tables, _ = read_dataset(tmp_path)
    assert all(r.ok for r in run_checks(tables))


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
