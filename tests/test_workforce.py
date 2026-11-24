import csv
import hashlib
import json
import re
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
    _demand,
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


def test_demand_shares_and_weekend_factor_for_100_people() -> None:
    staff = [{"skills": "RN"} for _ in range(100)]
    days = [date(2025, 6, 2), date(2025, 6, 7)]
    rows = _demand(staff, days)
    need = {(r["date"], r["shift_id"]): r["required"] for r in rows}
    assert need[("2025-06-02", "DAY")] == 25
    assert need[("2025-06-02", "EVE")] == 20
    assert need[("2025-06-02", "NIGHT")] == 10
    assert need[("2025-06-07", "DAY")] == 15
    assert need[("2025-06-07", "EVE")] == 12
    assert need[("2025-06-07", "NIGHT")] == 6


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
    ("kw", "message"),
    [
        ({"staff": 0}, "staff must be between 1 and 500"),
        ({"staff": MAX_STAFF + 1}, "staff must be between 1 and 500"),
        ({"days": 0}, "days must be between 1 and 366"),
        ({"days": MAX_DAYS + 1}, "days must be between 1 and 366"),
    ],
)
def test_input_limits(kw: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        generate_workforce(make(**kw))


def test_limits_accept_edges() -> None:
    one = generate_workforce(make(staff=1, days=1)).tables
    assert len(one["staff"]) == 1
    assert len(one["shifts"]) == 3
    assert len(one["availability"]) <= 1
    # one person
    assert [r["skills"] for r in one["staff"]] == ["RN"]
    assert len(one["demand"]) == 3
    assert {r["required"] for r in one["demand"]} == {1}
    many = generate_workforce(make(staff=MAX_STAFF, days=7)).tables
    assert len(many["staff"]) == MAX_STAFF
    assert {r["date"] for r in many["demand"]} == {
        (date(2025, 6, 2) + timedelta(days=i)).isoformat() for i in range(7)
    }
    long = generate_workforce(make(staff=5, days=MAX_DAYS)).tables
    assert len({r["date"] for r in long["demand"]}) == MAX_DAYS
    assert len(long["staff"]) == 5


def test_demand_hand_derived_for_20_staff() -> None:
    ds = generate_workforce(WorkforceParams(seed=42, staff=20, days=28))
    heads: dict[str, int] = {}
    for r in ds.tables["staff"]:
        for s in r["skills"].split("|"):
            heads[s] = heads.get(s, 0) + 1
    assert heads == {"RN": 12, "MA": 12, "FRONT": 4}
    need = {
        (r["date"], r["shift_id"], r["skill"]): r["required"]
        for r in ds.tables["demand"]
    }
    # weekday need
    monday = "2025-06-02"
    assert need[(monday, "DAY", "RN")] == 3
    assert need[(monday, "EVE", "MA")] == 2
    assert need[(monday, "NIGHT", "RN")] == 1
    assert need[(monday, "DAY", "FRONT")] == 1
    assert (monday, "NIGHT", "FRONT") not in need
    # weekend need
    saturday = "2025-06-07"
    assert need[(saturday, "DAY", "RN")] == 2
    assert need[(saturday, "EVE", "MA")] == 1
    assert need[(saturday, "NIGHT", "RN")] == 1
    assert need[(saturday, "DAY", "FRONT")] == 1
    # total rows
    assert sum(need.values()) == 360
    assert len(need) == 28 * 8


def test_availability_rates_over_many_seeds() -> None:
    counts = {"unavailable": 0, "prefer_off": 0, "prefer_on": 0}
    cells = 0
    for seed in range(50):
        ds = generate_workforce(WorkforceParams(seed=seed, staff=50, days=60))
        cells += 50 * 60
        for r in ds.tables["availability"]:
            counts[r["kind"]] += 1
    # sampling error
    assert abs(counts["unavailable"] / cells - 0.04) < 0.004
    assert abs(counts["prefer_off"] / cells - 0.08) < 0.004
    assert abs(counts["prefer_on"] / cells - 0.06) < 0.004


GOLDEN = {
    "staff": "072f4019b58847696d4b0f0d985b5f87bcad74873eee706ef30e3329a5c4f235",
    "shifts": "1047928ea888e9f2609ca3975b7b7d22e73bdc2623c53db1efb01d77684f3c1b",
    "demand": "60c6e42df06a8d576a30c2a54545f293506b1788145f117c25e7c8375a5f0ffa",
    "availability": "d76aa2f36423686ce63904a03b249e5e5cf73023cedda81d80e43196d03e2086",
}


def test_golden_hashes_seed_42(tmp_path: Path) -> None:
    ds = generate_workforce(WorkforceParams(seed=42, staff=20, days=28))
    write_workforce(ds, tmp_path)
    for name, digest in GOLDEN.items():
        data = (tmp_path / f"{name}.csv").read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
    # hand derived
    assert [len(ds.tables[n]) for n in TABLES] == [20, 3, 224, 103]
    first = ds.tables["staff"][0]
    assert first["staff_id"] == "S-0001"
    assert first["skills"] == "RN"
    assert first["cost_cents_hour"] == 4200


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
    with pytest.raises(FileExistsError, match=re.escape("is not empty")):
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


def test_cli_start_date_and_force(tmp_path: Path) -> None:
    out = tmp_path / "o"
    args = ["workforce", "--staff", "5", "--days", "3", "--out", str(out)]
    assert main([*args, "--start-date", "2026-03-02"]) == 0
    with (out / "demand.csv").open(newline="") as f:
        dates = {r["date"] for r in csv.DictReader(f)}
    assert dates == {"2026-03-02", "2026-03-03", "2026-03-04"}
    (out / "keep.txt").write_text("keep")
    assert main(args) == 1
    assert main([*args, "--force"]) == 0
    assert (out / "keep.txt").read_text() == "keep"
    with (out / "demand.csv").open(newline="") as f:
        assert "2025-06-02" in {r["date"] for r in csv.DictReader(f)}


def test_cli_bad_date_is_refused(tmp_path: Path) -> None:
    args = ["workforce", "--start-date", "02-06-2025", "--out", str(tmp_path / "o")]
    with pytest.raises(SystemExit) as e:
        main(args)
    assert e.value.code == 2
    assert not (tmp_path / "o").exists()


def test_start_date_overflow_message() -> None:
    msg = "start_date plus days must stay on or before 9999-12-31"
    with pytest.raises(ValueError, match=re.escape(msg)):
        generate_workforce(make(start_date=date(9999, 12, 30), days=28))


def test_last_valid_start_date() -> None:
    ds = generate_workforce(make(start_date=date(9999, 12, 4), days=28))
    assert max(r["date"] for r in ds.tables["demand"]) == "9999-12-31"
    with pytest.raises(ValueError):
        generate_workforce(make(start_date=date(9999, 12, 5), days=28))


def test_cli_date_overflow_is_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["workforce", "--start-date", "9999-12-30", "--days", "28"]
    assert main([*args, "--out", str(tmp_path / "x")]) == 1
    out = capsys.readouterr().out
    assert "must stay on or before 9999-12-31" in out
    assert "Traceback" not in out


def test_force_refuses_finance_folder(tmp_path: Path) -> None:
    main(["generate", "--out", str(tmp_path)])
    before = (tmp_path / "manifest.json").read_text()
    args = ["workforce", "--out", str(tmp_path), "--force"]
    assert main(args) == 1
    assert (tmp_path / "manifest.json").read_text() == before
    assert not (tmp_path / "staff.csv").exists()
