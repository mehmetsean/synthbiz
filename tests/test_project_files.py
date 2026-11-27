import ast
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz import __version__
from synthbiz.cli import main
from synthbiz.io import NOTICE
from synthbiz.mspdi import project_xml
from synthbiz.project import (
    FIRST_START,
    LAST_START,
    MAX_TASKS,
    MIN_TASKS,
    RANGE_COLUMNS,
    RISK_COLUMNS,
    Link,
    ProjectDataset,
    ProjectParams,
    Task,
    generate_project,
)
from synthbiz.project_files import known_files, write_project
from synthbiz.schema import DISCLAIMER

NS = "{http://schemas.microsoft.com/project}"
FILES = [
    "README.txt",
    "data_dictionary.md",
    "manifest.json",
    "project.xml",
    "ranges.csv",
    "risks.csv",
]


def tiny() -> ProjectDataset:
    tasks = [
        Task(1, "Phase 1: A & <B>", "1", 1, summary=True, cost_cents=500_050),
        Task(2, "Dig", "1.1", 2, False, False, 1_200, 100, 500_050),
        Task(3, "Done", "1.2", 2, milestone=True),
    ]
    links = [
        Link(2, 3, "FF", 0),
        Link(1, 3, "FS", -480),
        Link(2, 1, "SF", 960),
        Link(3, 2, "SS", 240),
    ]
    holiday = [(date(2025, 1, 20), "Martin Luther King Jr. Day")]
    return ProjectDataset(
        ProjectParams(1, 8), date(2025, 1, 6), 2026, holiday, tasks, links, [], []
    )


def child_tags(element: ET.Element) -> list[str]:
    return [c.tag.removeprefix(NS) for c in element]


def text(element: ET.Element, path: str) -> str:
    found = element.find("/".join(NS + p for p in path.split("/")))
    assert found is not None and found.text is not None, path
    return found.text


def every(element: ET.Element, path: str) -> list[ET.Element]:
    return element.findall("/".join(NS + p for p in path.split("/")))


def test_project_element_order() -> None:
    root = ET.fromstring(project_xml(tiny()))
    assert root.tag == NS + "Project"
    # schema order
    assert child_tags(root) == [
        "SaveVersion",
        "Name",
        "Title",
        "ScheduleFromStart",
        "StartDate",
        "CurrencyDigits",
        "CurrencyCode",
        "CalendarUID",
        "DefaultStartTime",
        "DefaultFinishTime",
        "MinutesPerDay",
        "MinutesPerWeek",
        "DaysPerMonth",
        "Calendars",
        "Tasks",
    ]
    assert text(root, "SaveVersion") == "12"
    assert text(root, "StartDate") == "2025-01-06T08:00:00"
    assert text(root, "CurrencyCode") == "USD"
    assert text(root, "CalendarUID") == "1"
    assert text(root, "MinutesPerDay") == "480"
    assert text(root, "MinutesPerWeek") == "2400"
    assert "synthetic data" in text(root, "Title")


def test_calendar_by_hand() -> None:
    root = ET.fromstring(project_xml(tiny()))
    (calendar,) = every(root, "Calendars/Calendar")
    assert child_tags(calendar) == [
        "UID",
        "Name",
        "IsBaseCalendar",
        "BaseCalendarUID",
        "WeekDays",
        "Exceptions",
    ]
    assert text(calendar, "UID") == "1"
    assert text(calendar, "BaseCalendarUID") == "-1"
    days = every(calendar, "WeekDays/WeekDay")
    assert [text(d, "DayType") for d in days] == ["1", "2", "3", "4", "5", "6", "7"]
    # Sunday=1
    assert [text(d, "DayWorking") for d in days] == list("0111110")
    for day in days:
        times = [
            (text(t, "FromTime"), text(t, "ToTime"))
            for t in every(day, "WorkingTimes/WorkingTime")
        ]
        if text(day, "DayWorking") == "1":
            assert times == [("08:00:00", "12:00:00"), ("13:00:00", "17:00:00")]
        else:
            assert times == []
    (holiday,) = every(calendar, "Exceptions/Exception")
    assert child_tags(holiday) == [
        "EnteredByOccurrences",
        "TimePeriod",
        "Occurrences",
        "Name",
        "Type",
        "DayWorking",
    ]
    assert text(holiday, "TimePeriod/FromDate") == "2025-01-20T00:00:00"
    assert text(holiday, "TimePeriod/ToDate") == "2025-01-20T23:59:00"
    assert text(holiday, "Occurrences") == "1"
    assert text(holiday, "Type") == "1"
    assert text(holiday, "DayWorking") == "0"


def test_tasks_and_links_by_hand() -> None:
    root = ET.fromstring(project_xml(tiny()))
    summary, work, done = every(root, "Tasks/Task")
    assert child_tags(summary) == [
        "UID",
        "ID",
        "Name",
        "WBS",
        "OutlineNumber",
        "OutlineLevel",
        "Milestone",
        "Summary",
        "FixedCost",
        "Cost",
        "PredecessorLink",
    ]
    assert child_tags(work) == [
        "UID",
        "ID",
        "Name",
        "WBS",
        "OutlineNumber",
        "OutlineLevel",
        "Duration",
        "DurationFormat",
        "Milestone",
        "Summary",
        "FixedCost",
        "Cost",
        "PredecessorLink",
    ]
    assert text(summary, "Name") == "Phase 1: A & <B>"
    assert text(summary, "Summary") == "1"
    assert text(summary, "OutlineLevel") == "1"
    assert text(work, "WBS") == "1.1"
    assert text(work, "OutlineNumber") == "1.1"
    assert text(work, "Duration") == "PT20H0M0S"
    assert text(work, "DurationFormat") == "7"
    # cents
    assert text(work, "FixedCost") == "100"
    assert text(work, "Cost") == "500050"
    assert text(done, "Milestone") == "1"
    assert text(done, "Duration") == "PT0H0M0S"
    got = {}
    for task in (summary, work, done):
        for link in every(task, "PredecessorLink"):
            assert child_tags(link) == [
                "PredecessorUID",
                "Type",
                "LinkLag",
                "LagFormat",
            ]
            key = (text(link, "PredecessorUID"), text(task, "UID"))
            got[key] = tuple(text(link, t) for t in ("Type", "LinkLag", "LagFormat"))
    # type codes
    assert got == {
        ("2", "3"): ("0", "0", "7"),
        ("1", "3"): ("1", "-4800", "7"),
        ("2", "1"): ("2", "9600", "7"),
        ("3", "2"): ("3", "2400", "7"),
    }


def test_xml_header_and_notice() -> None:
    data = project_xml(tiny())
    head = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<!-- '
    assert data.startswith(head)
    comment = data.decode("utf-8").split("-->")[0]
    assert DISCLAIMER in comment
    assert NOTICE in comment
    assert "--" not in comment.split("<!--")[1]
    assert data.endswith(b"</Project>\n")
    assert b"\r" not in data


@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=100_000),
    tasks=st.integers(min_value=8, max_value=120),
)
def test_xml_round_trip(seed: int, tasks: int) -> None:
    ds = generate_project(ProjectParams(seed, tasks))
    root = ET.fromstring(project_xml(ds))
    elements = every(root, "Tasks/Task")
    assert [int(text(e, "UID")) for e in elements] == [t.uid for t in ds.tasks]
    names = {"0": "FF", "1": "FS", "2": "SF", "3": "SS"}
    links = []
    for element, task in zip(elements, ds.tasks, strict=True):
        assert text(element, "Name") == task.name
        assert int(text(element, "Cost")) == task.cost_cents
        if not task.summary:
            match = re.fullmatch(r"PT([0-9]+)H([0-9]+)M0S", text(element, "Duration"))
            assert match
            minutes = int(match[1]) * 60 + int(match[2])
            assert minutes == task.duration_minutes
        for link in every(element, "PredecessorLink"):
            lag, rest = divmod(int(text(link, "LinkLag")), 10)
            assert rest == 0
            pred = int(text(link, "PredecessorUID"))
            links.append(Link(pred, task.uid, names[text(link, "Type")], lag))
    assert links == ds.links
    dates = [
        text(e, "TimePeriod/FromDate")[:10]
        for e in every(root, "Calendars/Calendar/Exceptions/Exception")
    ]
    assert dates == [d.isoformat() for d, _ in ds.holidays]


def make() -> ProjectDataset:
    return generate_project(ProjectParams(seed=5, tasks=30))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_write_files_and_manifest(tmp_path: Path) -> None:
    ds = make()
    write_project(ds, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == FILES
    assert sorted(known_files()) == FILES
    m = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    assert m["synthetic"] is True
    assert m["kind"] == "project"
    assert m["synthbiz_version"] == __version__
    assert m["parameters"] == {"seed": 5, "tasks": 30, "start_date": "2025-01-06"}
    assert m["project_start"] == "2025-01-06"
    assert m["holidays_listed_through_year"] == ds.holiday_end_year
    assert m["counts"] == {
        "tasks": 30,
        "summary_tasks": sum(t.summary for t in ds.tasks),
        "milestones": sum(t.milestone for t in ds.tasks),
        "links": len(ds.links),
        "holidays": len(ds.holidays),
        "ranges": len(ds.ranges),
        "risks": len(ds.risks),
    }
    assert m["units"] == {
        "ranges": "percent of plan duration",
        "risk_minutes": "working minutes",
        "risk_cents": "cents",
    }
    assert sorted(m["files"]) == [f for f in FILES if f != "manifest.json"]
    for name, digest in m["files"].items():
        data = (tmp_path / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
    for name in ("README.txt", "data_dictionary.md"):
        body = (tmp_path / name).read_text("utf-8")
        assert "synthetic data" in body.lower()
        assert DISCLAIMER in body
    assert NOTICE in (tmp_path / "README.txt").read_text("utf-8")
    assert "percent of plan duration" in (tmp_path / "README.txt").read_text("utf-8")


def test_csv_headers_and_rows(tmp_path: Path) -> None:
    ds = make()
    write_project(ds, tmp_path)
    head = (tmp_path / "ranges.csv").read_text("utf-8").splitlines()[0]
    assert head == "uid,dist,min,most_likely,max,corr_group"
    head = (tmp_path / "risks.csv").read_text("utf-8").splitlines()[0]
    assert head == (
        "risk_id,probability,impact_dist,min_minutes,most_likely_minutes,"
        "max_minutes,min_cents,most_likely_cents,max_cents,affected_uids,corr_group"
    )
    dictionary = (tmp_path / "data_dictionary.md").read_text("utf-8")
    for name, source in (("ranges", ds.ranges), ("risks", ds.risks)):
        section = dictionary.split(f"## {name}.csv")[1].split("\n## ")[0]
        for column in RANGE_COLUMNS if name == "ranges" else RISK_COLUMNS:
            assert f"`{column}`" in section
        want = [{k: str(v) for k, v in r.items()} for r in source]
        assert rows(tmp_path / f"{name}.csv") == want


COST_NOTE = (
    "A work task's Cost is FixedCost plus a day rate times its duration in days. "
    "The file holds no resources or assignments, so a tool that recomputes cost "
    "may get other totals."
)
LEAD_NOTE = (
    "A lead (negative lag) is never longer than the predecessor's duration, and "
    "a link from a milestone has no lead."
)


@pytest.mark.parametrize("name", ["README.md", "docs/adr/0019-project-schedules.md"])
def test_docs_state_cost_and_lead_rules(name: str) -> None:
    root = Path(__file__).resolve().parent.parent
    flat = " ".join((root / name).read_text("utf-8").split())
    assert COST_NOTE in flat
    assert LEAD_NOTE in flat


def test_unit_claim_always_names_its_limit() -> None:
    root = Path(__file__).resolve().parent.parent
    paths = [root / "README.md", root / "CHANGELOG.md", root / "DATA.md"]
    paths += sorted((root / "docs").rglob("*.md"))
    paths += sorted((root / "src").rglob("*.py"))
    seen = 0
    for path in paths:
        flat = " ".join(path.read_text("utf-8").split())
        for tail in flat.split("does not state the unit")[1:]:
            assert re.match(r"( of Cost and FixedCost)? on the pages named", tail)
            seen += 1
    assert seen >= 3


def test_dictionary_notice_and_caveats(tmp_path: Path) -> None:
    write_project(make(), tmp_path)
    body = (tmp_path / "data_dictionary.md").read_text("utf-8")
    assert f"Copyright (c) 2026 Mehmet Tuzunkan. {NOTICE}" in body.splitlines()
    flat = " ".join(body.split())
    for sentence in (
        "hundredths of the currency unit (cents). Microsoft does not state the unit "
        "on the pages named in docs/adr/0019-project-schedules.md of synthbiz.",
        COST_NOTE,
        LEAD_NOTE,
        "A group name is on at least two rows.",
        "The file has not been opened in Microsoft Project.",
        "For uniform, min and max are the bounds. most_likely is written but not used.",
        "Juneteenth from 2021",
    ):
        assert sentence in flat


def test_same_bytes_across_processes(tmp_path: Path) -> None:
    for name, hash_seed in (("a", "1"), ("b", "2")):
        command = [sys.executable, "-m", "synthbiz", "project", "--seed", "9"]
        command += ["--tasks", "200", "--out", str(tmp_path / name)]
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        subprocess.run(command, env=env, check=True, timeout=60)
    for name in FILES:
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name
        ).read_bytes()


GOLDEN = {
    "project.xml": ("f02f9dc2d905a687013d2977883084241f27cc232d9a3b2a1045b85dd4791813"),
    "ranges.csv": ("57c44f133b5df4f781558411b64656d86a9c3f06137d5e9390f90fc9fa4ad32a"),
    "risks.csv": ("98e616ec7e6c02411c83065b6f8380b7c7fc9b8fffae00645a22429d90b1123a"),
}


def test_golden_seed_42(tmp_path: Path) -> None:
    write_project(generate_project(ProjectParams(seed=42, tasks=50)), tmp_path)
    for name, digest in GOLDEN.items():
        data = (tmp_path / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
    # hand derived
    root = ET.fromstring((tmp_path / "project.xml").read_bytes())
    tasks = every(root, "Tasks/Task")
    assert len(tasks) == 50
    # 3 phases
    assert sum(text(t, "Summary") == "1" for t in tasks) == 3
    assert sum(text(t, "Milestone") == "1" for t in tasks) == 3
    assert [text(t, "UID") for t in tasks if text(t, "Summary") == "1"] == [
        "1",
        "18",
        "35",
    ]
    assert len(rows(tmp_path / "ranges.csv")) == 50 - 3 - 3
    assert [r["risk_id"] for r in rows(tmp_path / "risks.csv")] == [
        "R-0001",
        "R-0002",
        "R-0003",
    ]
    links = every(root, "Tasks/Task/PredecessorLink")
    kinds = Counter(text(x, "Type") for x in links)
    # README numbers
    assert len(links) == 75
    assert kinds == {"1": 65, "3": 7, "0": 2, "2": 1}
    assert sum(int(text(x, "LinkLag")) > 0 for x in links) == 11
    leads = {}
    for t in tasks:
        for x in every(t, "PredecessorLink"):
            if int(text(x, "LinkLag")) < 0:
                pred = tasks[int(text(x, "PredecessorUID")) - 1]
                leads[text(t, "UID")] = (text(x, "LinkLag"), text(pred, "Duration"))
    # one day
    assert leads == {
        "13": ("-4800", "PT96H0M0S"),
        "27": ("-4800", "PT56H0M0S"),
    }
    assert len(every(root, "Calendars/Calendar/Exceptions/Exception")) == 43
    first = every(root, "Calendars/Calendar/Exceptions/Exception")[0]
    assert text(first, "Name") == "Martin Luther King Jr. Day"


def test_force_keeps_other_files(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("keep", "utf-8")
    ds = make()
    with pytest.raises(FileExistsError, match=re.escape(f"{tmp_path} is not empty")):
        write_project(ds, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x.txt"]
    write_project(ds, tmp_path, force=True)
    write_project(ds, tmp_path, force=True)
    assert (tmp_path / "x.txt").read_text("utf-8") == "keep"


@pytest.mark.parametrize(
    "command", [["generate", "--months", "1"], ["workforce", "--days", "1"]]
)
def test_force_refuses_other_dataset_folders(
    tmp_path: Path, command: list[str]
) -> None:
    assert main([*command, "--out", str(tmp_path)]) == 0
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    msg = f"{tmp_path} holds a manifest.json that is not a project manifest"
    msg += ", use an empty folder"
    with pytest.raises(FileExistsError, match=re.escape(msg)):
        write_project(make(), tmp_path, force=True)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("raw", [b"{not json", b"[1, 2]", b"\xff\xfe\x00bad"])
def test_force_refuses_unreadable_manifest(tmp_path: Path, raw: bytes) -> None:
    (tmp_path / "manifest.json").write_bytes(raw)
    msg = f"{tmp_path} holds a manifest.json that is not a project manifest"
    with pytest.raises(FileExistsError, match=re.escape(msg)):
        write_project(make(), tmp_path, force=True)
    assert (tmp_path / "manifest.json").read_bytes() == raw


def test_workforce_force_refuses_project_folder(tmp_path: Path) -> None:
    write_project(make(), tmp_path)
    before = (tmp_path / "manifest.json").read_bytes()
    assert main(["workforce", "--out", str(tmp_path), "--force"]) == 1
    assert (tmp_path / "manifest.json").read_bytes() == before


def test_cli_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["project", "--seed", "3", "--tasks", "12", "--out", str(tmp_path)]
    assert main(args) == 0
    ds = generate_project(ProjectParams(3, 12))
    want = f"Wrote a project with 12 tasks, {len(ds.links)} links and 3 risks"
    assert want in capsys.readouterr().out
    assert main(args) == 1
    assert "is not empty" in capsys.readouterr().out
    assert main([*args, "--force"]) == 0


def test_cli_defaults_and_start_date(tmp_path: Path) -> None:
    assert main(["project", "--out", str(tmp_path / "a")]) == 0
    m = json.loads((tmp_path / "a" / "manifest.json").read_text("utf-8"))
    assert m["parameters"] == {"seed": 42, "tasks": 50, "start_date": "2025-01-06"}
    args = ["project", "--start-date", "2026-03-07", "--out", str(tmp_path / "b")]
    assert main(args) == 0
    m = json.loads((tmp_path / "b" / "manifest.json").read_text("utf-8"))
    assert m["parameters"]["start_date"] == "2026-03-07"
    assert m["project_start"] == "2026-03-09"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--tasks", "7"], "Error: tasks must be between 8 and 5000"),
        (["--tasks", "5001"], "Error: tasks must be between 8 and 5000"),
        (
            ["--start-date", "9999-12-31"],
            "Error: start_date must be between 2000-01-01 and 2099-12-31",
        ),
    ],
)
def test_cli_bad_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra: list[str],
    message: str,
) -> None:
    assert main(["project", *extra, "--out", str(tmp_path / "x")]) == 1
    assert capsys.readouterr().out == message + "\n"
    assert not (tmp_path / "x").exists()


def test_check_does_not_read_project_folders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_project(make(), tmp_path)
    assert main(["check", str(tmp_path)]) == 1
    want = f"Error: missing table file for chart_of_accounts in {tmp_path}\n"
    assert capsys.readouterr().out == want


def test_generate_force_has_no_kind_guard(tmp_path: Path) -> None:
    write_project(make(), tmp_path)
    names = ["README.txt", "data_dictionary.md", "manifest.json"]
    before = {n: (tmp_path / n).read_bytes() for n in names}
    xml = (tmp_path / "project.xml").read_bytes()
    args = ["generate", "--months", "1", "--out", str(tmp_path), "--force"]
    assert main(args) == 0
    for name in names:
        assert (tmp_path / name).read_bytes() != before[name]
    assert "fictional" in (tmp_path / "README.txt").read_text("utf-8")
    assert "## journal_lines" in (tmp_path / "data_dictionary.md").read_text("utf-8")
    m = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    assert "kind" not in m
    assert (tmp_path / "project.xml").read_bytes() == xml


def test_readme_states_the_limits_and_columns() -> None:
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    assert f"The task count is {MIN_TASKS} to {MAX_TASKS}" in readme
    dates = f"{FIRST_START.isoformat()} to {LAST_START.isoformat()}"
    assert f"The start date is {dates}." in readme
    assert f"ranges.csv ({', '.join(RANGE_COLUMNS)})" in readme
    assert f"risks.csv ({', '.join(RISK_COLUMNS)})" in readme


WRITERS = {
    "generate": (["generate", "--months", "1"], "journal_lines.csv"),
    "workforce": (["workforce", "--days", "1"], "staff.csv"),
    "project": (["project", "--tasks", "8"], "project.xml"),
}


@pytest.mark.parametrize(
    ("writer", "others"),
    [
        ("generate", ["project.xml", "ranges.csv", "staff.csv"]),
        ("workforce", ["labels.csv", "schema.json", "vendors.csv", "project.xml"]),
        ("project", ["labels.csv", "schema.json", "vendors.csv", "staff.csv"]),
    ],
)
def test_force_leaves_files_of_others(
    tmp_path: Path, writer: str, others: list[str]
) -> None:
    for name in others:
        (tmp_path / name).write_text("mine", "utf-8")
    command = WRITERS[writer][0]
    assert main([*command, "--out", str(tmp_path), "--force"]) == 0
    for name in others:
        assert (tmp_path / name).read_text("utf-8") == "mine"


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_force_replaces_a_link_not_its_target(tmp_path: Path, writer: str) -> None:
    command, name = WRITERS[writer]
    target = tmp_path / "target.txt"
    target.write_text("mine", "utf-8")
    out = tmp_path / "out"
    out.mkdir()
    (out / name).symlink_to(target)
    assert main([*command, "--out", str(out), "--force"]) == 0
    assert target.read_text("utf-8") == "mine"
    assert (out / name).is_file() and not (out / name).is_symlink()


@pytest.mark.parametrize("kind", ["folder", "fifo"])
@pytest.mark.parametrize("last", [False, True])
@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_force_refuses_odd_entries_first(
    tmp_path: Path,
    writer: str,
    last: bool,
    kind: str,
) -> None:
    command, first = WRITERS[writer]
    name = "manifest.json" if last else first
    kept = "README.txt"
    (tmp_path / kept).write_text("old", "utf-8")
    odd = tmp_path / name
    if kind == "folder":
        odd.mkdir()
    else:
        os.mkfifo(odd)
    full = [sys.executable, "-m", "synthbiz", *command]
    full += ["--out", str(tmp_path), "--force"]
    # no hang
    done = subprocess.run(full, capture_output=True, text=True, timeout=60)
    assert done.returncode == 1
    want = f"Error: {odd} is not a regular file or a link, "
    want += "move it or use another folder\n"
    assert done.stdout == want
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([kept, name])
    assert (tmp_path / kept).read_text("utf-8") == "old"


@pytest.mark.parametrize("value", ["", "   "])
@pytest.mark.parametrize("command", ["generate", "workforce", "project", "check"])
def test_empty_folder_path_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    value: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    args = [command, value] if command == "check" else [command, "--out", value]
    with pytest.raises(SystemExit) as e:
        main(args)
    assert e.value.code == 2
    assert "the folder path must not be empty" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_cli_negative_seed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["project", "--seed", "-1", "--out", str(tmp_path / "x")]) == 1
    assert capsys.readouterr().out == "Error: seed must be 0 or more\n"
    assert not (tmp_path / "x").exists()


@pytest.mark.parametrize("writer", ["workforce", "project"])
def test_deeply_nested_manifest_is_refused(tmp_path: Path, writer: str) -> None:
    raw = "[" * 200_000 + "]" * 200_000
    (tmp_path / "manifest.json").write_text(raw, "utf-8")
    command = WRITERS[writer][0]
    assert main([*command, "--out", str(tmp_path), "--force"]) == 1
    assert (tmp_path / "manifest.json").read_text("utf-8") == raw


def test_manifest_recursion_error_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(text: str) -> object:
        raise RecursionError

    (tmp_path / "manifest.json").write_text("{}", "utf-8")
    monkeypatch.setattr(json, "loads", boom)
    msg = f"{tmp_path} holds a manifest.json that is not a project manifest"
    with pytest.raises(FileExistsError, match=re.escape(msg)):
        write_project(make(), tmp_path, force=True)


def test_every_text_write_sets_the_line_end() -> None:
    root = Path(__file__).resolve().parent.parent
    seen = 0
    for folder in ("src", "scripts", "benchmarks"):
        for path in sorted((root / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text("utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                if getattr(node.func, "attr", "") != "write_text":
                    continue
                ends = [k.value for k in node.keywords if k.arg == "newline"]
                assert ends, f"{path.name} line {node.lineno}"
                assert isinstance(ends[0], ast.Constant) and ends[0].value == "\n"
                seen += 1
    assert seen >= 12


BAD_CHARS = ["\x00", "\x0b", "\x1f", "\ud800", "\udfff", "\ufffe", "\uffff"]


@pytest.mark.parametrize("bad", BAD_CHARS)
@pytest.mark.parametrize("place", ["task", "holiday"])
def test_xml_refuses_invalid_characters(bad: str, place: str) -> None:
    ds = tiny()
    if place == "task":
        ds.tasks[1].name = f"a{bad}b"
    else:
        ds.holidays = [(date(2025, 1, 20), bad)]
    msg = "Name holds a character that XML does not allow"
    with pytest.raises(ValueError, match=re.escape(msg)):
        project_xml(ds)


@settings(max_examples=200, deadline=None)
@given(name=st.text(min_size=1, max_size=8))
def test_xml_name_is_refused_or_kept(name: str) -> None:
    ds = tiny()
    ds.tasks[1].name = name
    allowed = all(
        c in "\t\n\r"
        or 0x20 <= ord(c) <= 0xD7FF
        or 0xE000 <= ord(c) <= 0xFFFD
        or ord(c) >= 0x10000
        for c in name
    )
    if not allowed:
        with pytest.raises(ValueError, match=re.escape("XML does not allow")):
            project_xml(ds)
        return
    work = every(ET.fromstring(project_xml(ds)), "Tasks/Task")[1]
    # line ends
    assert text(work, "Name") == name.replace("\r\n", "\n").replace("\r", "\n")


@pytest.mark.parametrize("writer", ["generate", "workforce"])
def test_other_commands_accept_a_negative_seed(tmp_path: Path, writer: str) -> None:
    # stated limit
    command = WRITERS[writer][0]
    assert main([*command, "--seed", "-1", "--out", str(tmp_path)]) == 0


def test_cli_out_is_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "f"
    target.write_text("keep", "utf-8")
    assert main(["project", "--out", str(target)]) == 1
    assert capsys.readouterr().out == f"Error: {target} is a file, not a folder\n"
    assert target.read_text("utf-8") == "keep"
