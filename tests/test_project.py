import re
from collections import Counter
from datetime import date, timedelta
from graphlib import CycleError, TopologicalSorter

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.dates import holidays, is_business_day
from synthbiz.project import (
    MAX_TASKS,
    MIN_TASKS,
    RANGE_COLUMNS,
    RISK_COLUMNS,
    Link,
    ProjectDataset,
    ProjectParams,
    generate_project,
)

Node = tuple[int, str]
# link ends
ENDS = {"FS": ("F", "S"), "SS": ("S", "S"), "FF": ("F", "F"), "SF": ("S", "F")}


def make(seed: int = 7, tasks: int = 60) -> ProjectDataset:
    return generate_project(ProjectParams(seed=seed, tasks=tasks))


def children(ds: ProjectDataset) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    parent = 0
    for t in ds.tasks:
        if t.summary:
            parent = t.uid
            out[parent] = []
        else:
            out[parent].append(t.uid)
    return out


def event_graph(ds: ProjectDataset, links: list[Link]) -> dict[Node, dict[Node, int]]:
    """Predecessor map."""
    graph: dict[Node, dict[Node, int]] = {
        (t.uid, end): {} for t in ds.tasks for end in "SF"
    }
    for t in ds.tasks:
        if not t.summary:
            graph[(t.uid, "F")][(t.uid, "S")] = t.duration_minutes
    for parent, kids in children(ds).items():
        for kid in kids:
            graph[(kid, "S")][(parent, "S")] = 0
            graph[(parent, "F")][(kid, "F")] = 0
    for link in links:
        a, b = ENDS[link.kind]
        graph[(link.succ_uid, b)][(link.pred_uid, a)] = link.lag_minutes
    return graph


def order(graph: dict[Node, dict[Node, int]]) -> list[Node]:
    return list(TopologicalSorter(graph).static_order())


def finish_minutes(ds: ProjectDataset) -> int:
    graph = event_graph(ds, ds.links)
    at: dict[Node, int] = {}
    for node in order(graph):
        at[node] = max([0] + [at[p] + w for p, w in graph[node].items()])
    return max(at.values())


def check_network(ds: ProjectDataset, tasks: int) -> None:
    by_uid = {t.uid: t for t in ds.tasks}
    assert [t.uid for t in ds.tasks] == list(range(1, tasks + 1))
    order(event_graph(ds, ds.links))
    pairs = [(x.pred_uid, x.succ_uid) for x in ds.links]
    assert len(set(pairs)) == len(pairs)
    assert all(a != b and a in by_uid and b in by_uid for a, b in pairs)
    assert {x.kind for x in ds.links} == {"FS", "SS", "FF", "SF"}
    assert any(x.lag_minutes > 0 for x in ds.links)
    assert any(x.lag_minutes < 0 for x in ds.links)
    assert all(x.kind == "FS" for x in ds.links if x.lag_minutes < 0)
    kids = children(ds)
    on_summary = [
        x for x in ds.links if by_uid[x.pred_uid].summary or by_uid[x.succ_uid].summary
    ]
    assert on_summary
    for x in on_summary:
        assert x.kind in ("FS", "SS")
        assert x.succ_uid not in kids.get(x.pred_uid, [])
        assert x.pred_uid not in kids.get(x.succ_uid, [])
    work = [t for t in ds.tasks if not t.summary and not t.milestone]
    drives = {x.pred_uid for x in ds.links if x.kind in ("FS", "FF")}
    assert all(t.uid in drives for t in work)


def check_tasks(ds: ProjectDataset) -> None:
    by_uid = {t.uid: t for t in ds.tasks}
    for parent, kids in children(ds).items():
        p = by_uid[parent]
        assert kids and p.level == 1 and not p.milestone
        assert p.fixed_cost_cents == 0 and p.duration_minutes == 0
        assert p.cost_cents == sum(by_uid[k].cost_cents for k in kids)
        assert by_uid[kids[-1]].milestone
    for t in ds.tasks:
        assert t.name
        if t.summary:
            continue
        assert t.level == 2
        if t.milestone:
            assert t.duration_minutes == 0
            assert t.cost_cents == t.fixed_cost_cents >= 0
        else:
            assert t.duration_minutes > 0 and t.duration_minutes % 240 == 0
            assert t.cost_cents > t.fixed_cost_cents >= 0


def check_tables(ds: ProjectDataset) -> None:
    work = {t.uid for t in ds.tasks if not t.summary and not t.milestone}
    assert [r["uid"] for r in ds.ranges] == sorted(work)
    for r in ds.ranges:
        assert list(r) == RANGE_COLUMNS
        assert r["dist"] in ("triangular", "pert", "uniform")
        assert 0 < r["min"] <= r["most_likely"] <= r["max"] <= 200
        assert r["min"] < r["max"]
        assert re.fullmatch(r"|G[0-9]+", r["corr_group"])
    ids = [r["risk_id"] for r in ds.risks]
    assert ids and len(set(ids)) == len(ids)
    for r in ds.risks:
        assert list(r) == RISK_COLUMNS
        assert re.fullmatch(r"0\.[0-9]{2}", r["probability"])
        assert 0 < float(r["probability"]) < 1
        assert r["impact_dist"] in ("triangular", "pert", "uniform")
        for unit in ("minutes", "cents"):
            low = r[f"min_{unit}"]
            mid = r[f"most_likely_{unit}"]
            high = r[f"max_{unit}"]
            assert 0 <= low <= mid <= high and low < high
        uids = [int(x) for x in r["affected_uids"].split("|")]
        assert uids and uids == sorted(set(uids)) and set(uids) <= work
        assert re.fullmatch(r"|RG[0-9]+", r["corr_group"])
    for row in ds.ranges + ds.risks:
        for value in row.values():
            assert not str(value).startswith(("=", "+", "-", "@", "\t", "\r"))


def check_calendar(ds: ProjectDataset) -> None:
    assert is_business_day(ds.start)
    assert ds.holidays == sorted(ds.holidays)
    for day, name in ds.holidays:
        assert day.weekday() < 5 and day >= ds.start
        assert holidays(day.year)[day] == name
    # full horizon
    last = date(ds.holiday_end_year, 12, 31)
    listed = {day for day, _ in ds.holidays}
    working = 0
    day = ds.start
    while day <= last:
        if day.weekday() < 5:
            assert (day in listed) == (not is_business_day(day))
        working += is_business_day(day)
        day += timedelta(days=1)
    assert working * 480 >= 2 * finish_minutes(ds)


@settings(max_examples=60, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=100_000),
    tasks=st.integers(min_value=MIN_TASKS, max_value=150),
)
def test_properties_for_any_seed_and_size(seed: int, tasks: int) -> None:
    ds = generate_project(ProjectParams(seed=seed, tasks=tasks))
    assert ds == generate_project(ProjectParams(seed=seed, tasks=tasks))
    check_network(ds, tasks)
    check_tasks(ds)
    check_tables(ds)


@settings(max_examples=8, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=100_000),
    tasks=st.integers(min_value=MIN_TASKS, max_value=150),
    start=st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31)),
)
def test_calendar_for_any_start(seed: int, tasks: int, start: date) -> None:
    ds = generate_project(ProjectParams(seed, tasks, start))
    check_calendar(ds)
    assert ds.start >= start


def test_smallest_sizes_over_many_seeds() -> None:
    for tasks in range(MIN_TASKS, 16):
        for seed in range(100):
            ds = make(seed, tasks)
            check_network(ds, tasks)
            check_tasks(ds)
            check_tables(ds)


def test_largest_size() -> None:
    ds = make(1, MAX_TASKS)
    assert len(ds.tasks) == 5000
    check_network(ds, 5000)
    check_tasks(ds)
    check_tables(ds)
    check_calendar(ds)
    assert len(ds.links) < 3 * 5000
    assert len(ds.risks) == 200
    # short horizon
    assert ds.holiday_end_year - ds.start.year < 25


def test_eight_tasks_by_hand() -> None:
    ds = make(42, 8)
    assert [t.summary for t in ds.tasks] == [True, False, False, False] * 2
    assert [t.milestone for t in ds.tasks] == [False, False, False, True] * 2
    assert [t.level for t in ds.tasks] == [1, 2, 2, 2] * 2
    wbs = ["1", "1.1", "1.2", "1.3", "2", "2.1", "2.2", "2.3"]
    assert [t.wbs for t in ds.tasks] == wbs
    assert ds.tasks[3].name == "Phase 1 complete"
    assert ds.tasks[7].name == "Phase 2 complete"
    assert [r["uid"] for r in ds.ranges] == [2, 3, 6, 7]
    assert len(ds.risks) == 3
    pairs = {(x.pred_uid, x.succ_uid) for x in ds.links}
    # fixed links
    assert {(2, 3), (4, 6), (6, 7), (1, 5), (7, 8)} <= pairs


def test_cycle_check_can_fail() -> None:
    ds = make()
    there = Link(2, 3, "FS", 0)
    back = Link(3, 2, "FS", 0)
    with pytest.raises(CycleError):
        order(event_graph(ds, [there, back]))
    # own child
    with pytest.raises(CycleError):
        order(event_graph(ds, [Link(1, 2, "FS", 0)]))


def test_other_seed_other_content() -> None:
    a, b = make(1), make(2)
    assert [t.name for t in a.tasks] != [t.name for t in b.tasks]
    assert a.links != b.links
    assert a.ranges != b.ranges
    assert a.risks != b.risks


def test_link_mix_is_mostly_finish_to_start() -> None:
    kinds = Counter(x.kind for x in make(3, 2000).links)
    assert kinds["FS"] > sum(kinds.values()) / 2
    assert min(kinds.values()) > 20


def test_start_moves_to_a_working_day() -> None:
    saturday = generate_project(ProjectParams(1, 8, date(2025, 1, 4)))
    assert saturday.start == date(2025, 1, 6)
    holiday = generate_project(ProjectParams(1, 8, date(2025, 1, 20)))
    assert holiday.start == date(2025, 1, 21)


def test_holidays_by_hand() -> None:
    ds = generate_project(ProjectParams(1, 8, date(2025, 1, 6)))
    days = [d for d, _ in ds.holidays]
    assert days[:3] == [date(2025, 1, 20), date(2025, 2, 17), date(2025, 5, 26)]
    assert date(2025, 1, 1) not in days


@pytest.mark.parametrize("tasks", [MIN_TASKS - 1, MAX_TASKS + 1, 0, -5])
def test_task_limits(tasks: int) -> None:
    msg = "tasks must be between 8 and 5000"
    with pytest.raises(ValueError, match=re.escape(msg)):
        generate_project(ProjectParams(1, tasks))


@pytest.mark.parametrize("start", [date(1999, 12, 31), date(2100, 1, 1)])
def test_start_date_limits(start: date) -> None:
    msg = "start_date must be between 2000-01-01 and 2099-12-31"
    with pytest.raises(ValueError, match=re.escape(msg)):
        generate_project(ProjectParams(1, 8, start))


def test_start_date_edges() -> None:
    for start in (date(2000, 1, 1), date(2099, 12, 31)):
        ds = generate_project(ProjectParams(1, MAX_TASKS, start))
        assert ds.start >= start
