import csv
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

import synthbiz.demo
from synthbiz.check import Result
from synthbiz.demo import MAX_MESSAGES, demo_zip, run_demo
from synthbiz.generate import Params, generate
from synthbiz.io import verify_manifest, write_dataset
from synthbiz.schema import TABLE_NAMES, money_columns

ARGS = (42, 3, "small", 0.05)


def test_run_demo_shape() -> None:
    data = json.loads(run_demo(*ARGS))
    assert list(data["tables"]) == TABLE_NAMES
    for t in data["tables"].values():
        assert len(t["preview"]) <= 5
        assert t["rows"] >= len(t["preview"])
    assert data["anomaly_count"] == len(data["labels"])
    rules = [c["rule"] for c in data["checks"]]
    assert rules[-1] == "manifest"
    assert all(c["ok"] for c in data["checks"])


def test_money_columns_come_from_schema() -> None:
    data = json.loads(run_demo(*ARGS))
    for name, t in data["tables"].items():
        assert t["money"] == money_columns(name)
        for col in t["money"]:
            assert all(re.fullmatch(r"-?\d+", str(r[col])) for r in t["preview"])
    assert data["tables"]["journal_lines"]["money"] == ["debit_cents", "credit_cents"]


def test_preview_rows() -> None:
    data = json.loads(run_demo(*ARGS, preview_rows=2))
    assert len(data["tables"]["journal_lines"]["preview"]) == 2


def test_run_demo_is_deterministic() -> None:
    assert run_demo(*ARGS) == run_demo(*ARGS)
    assert run_demo(*ARGS) != run_demo(7, 3, "small", 0.05)


def test_zip_is_deterministic() -> None:
    assert demo_zip(*ARGS) == demo_zip(*ARGS)


def test_zip_matches_cli_write(tmp_path: Path) -> None:
    ds = generate(Params(seed=42, months=3, size="small", anomaly_rate=0.05))
    write_dataset(ds, tmp_path / "cli")
    with zipfile.ZipFile(io.BytesIO(demo_zip(*ARGS))) as z:
        names = z.namelist()
        assert names == sorted(names)
        z.extractall(tmp_path / "zip")
    for name in names:
        assert (tmp_path / "zip" / name).read_bytes() == (
            tmp_path / "cli" / name
        ).read_bytes()
    assert verify_manifest(tmp_path / "zip") == []


@pytest.mark.parametrize(
    "args",
    [
        (-1, 3, "small", 0.02),
        (True, 3, "small", 0.02),
        (1.5, 3, "small", 0.02),
        (1, 0, "small", 0.02),
        (1, 25, "small", 0.02),
        (1, "3", "small", 0.02),
        (1, 3, "huge", 0.02),
        (1, 3, "small", 0.5),
        (1, 3, "small", -0.1),
        (1, 3, "small", "x"),
    ],
)
def test_bad_inputs(args: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        run_demo(*args)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        demo_zip(*args)  # type: ignore[arg-type]


def test_messages_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = Result("fake", False, [f"problem {i}" for i in range(8)])
    monkeypatch.setattr(synthbiz.demo, "run_checks", lambda tables, labels: [bad])
    data = json.loads(run_demo(*ARGS))
    fake = data["checks"][0]
    assert fake["ok"] is False
    assert fake["messages"] == [f"problem {i}" for i in range(MAX_MESSAGES)]


def test_zip_keeps_raw_cents() -> None:
    with zipfile.ZipFile(io.BytesIO(demo_zip(*ARGS))) as z:
        text = z.read("journal_lines.csv").decode()
    lines = text.splitlines()
    head = lines[0].split(",")
    col = head.index("debit_cents")
    assert len(lines) > 1
    for row in csv.reader(lines[1:]):
        assert re.fullmatch(r"-?[0-9]+", row[col])
