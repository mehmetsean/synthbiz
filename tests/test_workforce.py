import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.cli import main
from synthbiz.workforce import (
    MAX_DAYS,
    MAX_STAFF,
    TABLES,
    WorkforceParams,
    generate_workforce,
    known_files,
    write_workforce,
)

KINDS = {"unavailable", "prefer_off", "prefer_on"}


def make(**kw: object) -> WorkforceParams:
    base: dict[str, object] = {"seed": 7, "staff": 20, "days": 14}
    base.update(kw)
    return WorkforceParams(**base)  # type: ignore[arg-type]


def test_same_seed_same_tables() -> None:
    assert generate_workforce(make()).tables == generate_workforce(make()).tables


def test_other_seed_other_tables() -> None:
    a = generate_workforce(make(seed=1)).tables["staff"]
    b = generate_workforce(make(seed=2)).tables["staff"]
    assert a != b


def test_columns() -> None:
    ds = generate_workforce(make())
    for name, cols in TABLES.items():
        assert ds.tables[name]
        for row in ds.tables[name]:
            assert list(row) == cols


def test_staff_ranges() -> None:
    ds = generate_workforce(make(staff=40))
    staff = ds.tables["staff"]
    assert len(staff) == 40
    assert len({r["staff_id"] for r in staff}) == 40
    assert len({r["display_name"] for r in staff}) == 40
    for r in staff:
        assert r["skills"] and all(s for s in r["skills"].split("|"))
        assert 0 <= r["min_minutes_week"] <= r["max_minutes_week"] <= 7 * 1440
        assert r["max_minutes_week"] > 0
        assert 1000 <= r["cost_cents_hour"] <= 10_000
        assert 1 <= r["max_consecutive_days"] <= 7
        for k in ("min_minutes_week", "max_minutes_week", "cost_cents_hour"):
            assert isinstance(r[k], int)


def test_shifts_cross_midnight_flag() -> None:
    shifts = generate_workforce(make()).tables["shifts"]
    assert {r["shift_id"] for r in shifts} == {"DAY", "EVE", "NIGHT"}
    for r in shifts:
        assert 0 <= r["start"] < 1440
        assert 0 <= r["end"] < 1440
        assert r["start"] != r["end"]
        assert r["crosses_midnight"] == (1 if r["end"] < r["start"] else 0)
    assert [r["crosses_midnight"] for r in shifts] == [0, 0, 1]


def test_demand_weekday_and_weekend_patterns() -> None:
    ds = generate_workforce(make(staff=30, days=14, start_date=date(2025, 6, 2)))
    shift_ids = {r["shift_id"] for r in ds.tables["shifts"]}
    skills = {s for r in ds.tables["staff"] for s in r["skills"].split("|")}
    by_day: dict[date, int] = {}
    for r in ds.tables["demand"]:
        d = date.fromisoformat(r["date"])
        assert r["shift_id"] in shift_ids
        assert r["skill"] in skills
        assert r["required"] >= 1
        by_day[d] = by_day.get(d, 0) + r["required"]
    assert set(by_day) == {date(2025, 6, 2) + timedelta(days=i) for i in range(14)}
    weekday = {v for d, v in by_day.items() if d.weekday() < 5}
    weekend = {v for d, v in by_day.items() if d.weekday() >= 5}
    assert len(weekday) == 1 and len(weekend) == 1
    assert max(weekend) < min(weekday)


def test_demand_never_above_headcount() -> None:
    ds = generate_workforce(make(staff=3))
    heads: dict[str, int] = {}
    for r in ds.tables["staff"]:
        for s in r["skills"].split("|"):
            heads[s] = heads.get(s, 0) + 1
    for r in ds.tables["demand"]:
        assert r["required"] <= heads[r["skill"]]


def test_availability_keys_and_kinds() -> None:
    ds = generate_workforce(make(staff=30, days=28))
    rows = ds.tables["availability"]
    assert rows
    ids = {r["staff_id"] for r in ds.tables["staff"]}
    shift_ids = {r["shift_id"] for r in ds.tables["shifts"]} | {"*"}
    start = date.fromisoformat(ds.tables["demand"][0]["date"])
    keys = set()
    for r in rows:
        assert r["staff_id"] in ids
        assert r["shift_id"] in shift_ids
        assert r["kind"] in KINDS
        assert 0 <= (date.fromisoformat(r["date"]) - start).days < 28
        keys.add((r["staff_id"], r["date"], r["shift_id"]))
    assert len(keys) == len(rows)
    assert {r["kind"] for r in rows} == KINDS


def test_one_availability_row_per_person_day() -> None:
    rows = generate_workforce(make(staff=30, days=28)).tables["availability"]
    pairs = {(r["staff_id"], r["date"]) for r in rows}
    assert len(pairs) == len(rows)


def test_start_date_is_used() -> None:
    ds = generate_workforce(make(start_date=date(2026, 3, 2)))
    assert min(r["date"] for r in ds.tables["demand"]) == "2026-03-02"


@pytest.mark.parametrize(
    "kw",
    [
        {"staff": 0},
        {"staff": MAX_STAFF + 1},
        {"days": 0},
        {"days": MAX_DAYS + 1},
    ],
)
def test_input_limits(kw: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        generate_workforce(make(**kw))


def test_limits_accept_edges() -> None:
    generate_workforce(make(staff=1, days=1))
    generate_workforce(make(staff=MAX_STAFF, days=7))
    generate_workforce(make(staff=5, days=MAX_DAYS))


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    staff=st.integers(min_value=1, max_value=80),
    days=st.integers(min_value=1, max_value=30),
)
def test_properties_for_any_size(seed: int, staff: int, days: int) -> None:
    a = generate_workforce(WorkforceParams(seed=seed, staff=staff, days=days))
    b = generate_workforce(WorkforceParams(seed=seed, staff=staff, days=days))
    assert a.tables == b.tables
    assert len(a.tables["staff"]) == staff
    ids = {r["staff_id"] for r in a.tables["staff"]}
    assert all(r["staff_id"] in ids for r in a.tables["availability"])
    assert all(
        r["min_minutes_week"] <= r["max_minutes_week"] for r in a.tables["staff"]
    )
    assert {r["date"] for r in a.tables["demand"]} <= {
        (date(2025, 6, 2) + timedelta(days=i)).isoformat() for i in range(days)
    }


def test_write_files_and_manifest(tmp_path: Path) -> None:
    ds = generate_workforce(make())
    write_workforce(ds, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(known_files())
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["synthetic"] is True
    assert m["parameters"] == {
        "seed": 7,
        "staff": 20,
        "days": 14,
        "start_date": "2025-06-02",
    }
    for name, digest in m["files"].items():
        data = (tmp_path / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
    assert "synthetic" in (tmp_path / "README.txt").read_text().lower()
    assert "All rights reserved" in (tmp_path / "README.txt").read_text()


def test_csv_round_trip_and_bytes_are_stable(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    write_workforce(generate_workforce(make()), a)
    write_workforce(generate_workforce(make()), b)
    for name in known_files():
        assert (a / name).read_bytes() == (b / name).read_bytes()
    with (a / "staff.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == TABLES["staff"]
    assert len(rows) == 20


def test_write_refuses_non_empty_folder(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("keep")
    ds = generate_workforce(make())
    with pytest.raises(FileExistsError):
        write_workforce(ds, tmp_path)
    write_workforce(ds, tmp_path, force=True)
    assert (tmp_path / "x.txt").read_text() == "keep"


def test_cli_workforce(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["workforce", "--seed", "3", "--staff", "12", "--days", "7"]
    assert main([*args, "--out", str(tmp_path)]) == 0
    assert "Wrote 4 tables" in capsys.readouterr().out
    assert main([*args, "--out", str(tmp_path)]) == 1
    assert "not empty" in capsys.readouterr().out
    assert main(["workforce", "--staff", "0", "--out", str(tmp_path / "n")]) == 1
    assert "staff must be" in capsys.readouterr().out
