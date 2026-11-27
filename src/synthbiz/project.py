"""Project schedule."""

import random
from dataclasses import dataclass
from datetime import date
from math import isqrt
from typing import Any

from .dates import business_days, holidays, next_business_day
from .names import phase_name, task_name

MIN_TASKS = 8
MAX_TASKS = 5000
FIRST_START = date(2000, 1, 1)
LAST_START = date(2099, 12, 31)
DAY_MINUTES = 480
HALF_DAY = 240
MAX_PHASES = 10
LINK_KINDS = ("FS", "SS", "FF", "SF")
KIND_WEIGHTS = (70, 15, 10, 5)
DISTS = ("triangular", "pert", "uniform")
# calendar margin
HORIZON_FACTOR = 3

RANGE_COLUMNS = ["uid", "dist", "min", "most_likely", "max", "corr_group"]
RISK_COLUMNS = [
    "risk_id",
    "probability",
    "impact_dist",
    "min_minutes",
    "most_likely_minutes",
    "max_minutes",
    "min_cents",
    "most_likely_cents",
    "max_cents",
    "affected_uids",
    "corr_group",
]


@dataclass(frozen=True)
class ProjectParams:
    seed: int = 42
    tasks: int = 50
    start_date: date = date(2025, 1, 6)


@dataclass
class Task:
    uid: int
    name: str
    wbs: str
    level: int
    summary: bool = False
    milestone: bool = False
    duration_minutes: int = 0
    fixed_cost_cents: int = 0
    cost_cents: int = 0


@dataclass(frozen=True)
class Link:
    pred_uid: int
    succ_uid: int
    kind: str
    lag_minutes: int


@dataclass
class ProjectDataset:
    params: ProjectParams
    start: date
    holiday_end_year: int
    holidays: list[tuple[date, str]]
    tasks: list[Task]
    links: list[Link]
    ranges: list[dict[str, Any]]
    risks: list[dict[str, Any]]


# layers of uids
Phase = list[list[int]]


def _work_task(rng: random.Random, uid: int, wbs: str) -> Task:
    if rng.random() < 0.1:
        duration = HALF_DAY
    else:
        duration = rng.randint(1, 15) * DAY_MINUTES
    fixed = rng.randrange(50_000, 2_000_001, 100) if rng.random() < 0.4 else 0
    day_rate = rng.randrange(40_000, 400_001, 100)
    cost = fixed + day_rate * duration // DAY_MINUTES
    return Task(uid, task_name(rng), wbs, 2, False, False, duration, fixed, cost)


def _outline(rng: random.Random, count: int) -> tuple[list[Task], list[Phase]]:
    phases = max(2, min(MAX_PHASES, isqrt(count) // 2))
    # summaries and milestones
    work = count - 2 * phases
    tasks: list[Task] = []
    plan: list[Phase] = []
    for p in range(1, phases + 1):
        size = work // phases + (1 if p <= work % phases else 0)
        summary = Task(len(tasks) + 1, phase_name(rng, p), str(p), 1, summary=True)
        tasks.append(summary)
        depth = min(size, rng.randint(4, 6))
        widths = [1] * depth
        for _ in range(size - depth):
            widths[rng.randrange(depth)] += 1
        layers: Phase = []
        child = 0
        for width in widths:
            layer = []
            for _ in range(width):
                child += 1
                t = _work_task(rng, len(tasks) + 1, f"{p}.{child}")
                tasks.append(t)
                layer.append(t.uid)
            layers.append(layer)
        fee = rng.randrange(100_000, 1_000_001, 100) if rng.random() < 0.3 else 0
        end = Task(
            len(tasks) + 1,
            f"Phase {p} complete",
            f"{p}.{child + 1}",
            2,
            milestone=True,
            fixed_cost_cents=fee,
            cost_cents=fee,
        )
        tasks.append(end)
        layers.append([end.uid])
        summary.cost_cents = sum(t.cost_cents for t in tasks[summary.uid :])
        plan.append(layers)
    return tasks, plan


def _work_pairs(rng: random.Random, plan: list[Phase]) -> list[tuple[int, int]]:
    """Links into work."""
    pairs: dict[tuple[int, int], None] = {}
    for p, layers in enumerate(plan):
        body = layers[:-1]
        for j, layer in enumerate(body):
            for uid in layer:
                if j > 0:
                    pairs[(rng.choice(body[j - 1]), uid)] = None
                elif p > 0:
                    pairs[(plan[p - 1][-1][0], uid)] = None
                if j > 0 and rng.random() < 0.5:
                    near = body[rng.randrange(max(0, j - 3), j)]
                    pairs[(rng.choice(near), uid)] = None
                if p > 0 and rng.random() < 0.1:
                    earlier = rng.choice(plan[p - 1][:-1])
                    pairs[(rng.choice(earlier), uid)] = None
    flat = [(n, uid) for n, layer in enumerate(_all_layers(plan)) for uid in layer]
    ends = {layers[-1][0] for layers in plan}
    # small networks
    while len(pairs) < len(LINK_KINDS):
        (a, pred), (b, succ) = rng.sample(flat, 2)
        if a < b and succ not in ends:
            pairs[(pred, succ)] = None
    return list(pairs)


def _all_layers(plan: list[Phase]) -> list[list[int]]:
    return [layer for layers in plan for layer in layers]


def _lag(rng: random.Random, kind: str) -> int:
    x = rng.random()
    if x < 0.75:
        return 0
    if x < 0.93 or kind != "FS":
        return rng.randint(1, 5) * DAY_MINUTES
    return -rng.randint(1, 2) * DAY_MINUTES


def _typed_links(rng: random.Random, pairs: list[tuple[int, int]]) -> list[Link]:
    first = list(LINK_KINDS)
    rng.shuffle(first)
    picks = rng.sample(range(len(pairs)), len(first))
    forced = dict(zip(picks, first, strict=True))
    links = []
    for i, (pred, succ) in enumerate(pairs):
        kind = forced.get(i) or rng.choices(LINK_KINDS, KIND_WEIGHTS)[0]
        lag = _lag(rng, kind)
        # one lead, one lag
        if i in forced and kind == "FS":
            lag = -DAY_MINUTES
        if i in forced and kind == "SS":
            lag = 2 * DAY_MINUTES
        links.append(Link(pred, succ, kind, lag))
    return links


def _milestone_links(plan: list[Phase], links: list[Link]) -> list[Link]:
    drives = {x.pred_uid for x in links if x.kind in ("FS", "FF")}
    out = []
    for layers in plan:
        end = layers[-1][0]
        for j, layer in enumerate(layers[:-1]):
            for uid in layer:
                if j == len(layers) - 2 or uid not in drives:
                    out.append(Link(uid, end, "FS", 0))
    return out


def _summary_links(rng: random.Random, plan: list[Phase]) -> list[Link]:
    out = []
    # summary uid
    heads = [layers[0][0] - 1 for layers in plan]
    for p in range(1, len(plan)):
        if p > 1 and rng.random() < 0.5:
            continue
        pred, succ = heads[p - 1], heads[p]
        form = (p - 1) % 3
        if form == 1:
            succ = rng.choice(plan[p][0])
        if form == 2:
            pred = rng.choice(plan[p - 1][0])
        kind = rng.choice(("FS", "SS"))
        lag = rng.randint(0, 3) * DAY_MINUTES
        out.append(Link(pred, succ, kind, lag))
    return out


def _bound_minutes(tasks: list[Task], plan: list[Phase], links: list[Link]) -> int:
    """Longest path bound."""
    lag_in: dict[int, int] = {}
    for x in links:
        lag_in[x.succ_uid] = max(lag_in.get(x.succ_uid, 0), x.lag_minutes)
    total = 0
    for layers in plan:
        head = layers[0][0] - 1
        total += lag_in.get(head, 0)
        for layer in layers:
            total += max(tasks[u - 1].duration_minutes for u in layer)
            total += max(lag_in.get(u, 0) for u in layer)
    return total


def _calendar(start: date, minutes: int) -> tuple[int, list[tuple[date, str]]]:
    needed = HORIZON_FACTOR * (minutes // DAY_MINUTES + 1)
    year = start.year
    have = len(business_days(start, date(year, 12, 31)))
    while have < needed:
        year += 1
        have += len(business_days(date(year, 1, 1), date(year, 12, 31)))
    # spare year
    year += 1
    days = [
        (d, name)
        for y in range(start.year, year + 1)
        for d, name in holidays(y).items()
        if d >= start
    ]
    return year, days


def _ranges(rng: random.Random, plan: list[Phase]) -> list[dict[str, Any]]:
    rows = []
    for p, layers in enumerate(plan, start=1):
        for layer in layers[:-1]:
            for uid in layer:
                rows.append(
                    {
                        "uid": uid,
                        "dist": rng.choice(DISTS),
                        "min": rng.randrange(60, 96, 5),
                        "most_likely": rng.choice((100, 100, 100, 110)),
                        "max": rng.randrange(115, 181, 5),
                        "corr_group": f"G{p}" if rng.random() < 0.4 else "",
                    }
                )
    return rows


def _triple(rng: random.Random, step: int, top: int) -> tuple[int, int, int]:
    low = step * rng.randint(0, top)
    mid = low + step * rng.randint(1, top)
    return low, mid, mid + step * rng.randint(1, 2 * top)


def _risks(rng: random.Random, work: list[int], count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, count + 1):
        dist = rng.choice(DISTS)
        probability = f"0.{rng.randrange(5, 45, 5):02d}"
        minutes = _triple(rng, HALF_DAY, 5)
        cents = _triple(rng, 10_000, 50)
        hit = rng.sample(work, min(rng.randint(1, 5), len(work)))
        group = f"RG{rng.randint(1, 2)}" if rng.random() < 0.3 else ""
        values = [f"R-{i:04d}", probability, dist, *minutes, *cents]
        values += ["|".join(str(u) for u in sorted(hit)), group]
        rows.append(dict(zip(RISK_COLUMNS, values, strict=True)))
    return rows


def generate_project(params: ProjectParams) -> ProjectDataset:
    if not MIN_TASKS <= params.tasks <= MAX_TASKS:
        raise ValueError(f"tasks must be between {MIN_TASKS} and {MAX_TASKS}")
    if not FIRST_START <= params.start_date <= LAST_START:
        raise ValueError(
            f"start_date must be between {FIRST_START.isoformat()} "
            f"and {LAST_START.isoformat()}"
        )
    rng = random.Random(params.seed)
    tasks, plan = _outline(rng, params.tasks)
    links = _typed_links(rng, _work_pairs(rng, plan))
    links += _milestone_links(plan, links)
    links += _summary_links(rng, plan)
    links.sort(key=lambda x: (x.succ_uid, x.pred_uid))
    start = next_business_day(params.start_date)
    end_year, days = _calendar(start, _bound_minutes(tasks, plan, links))
    ranges = _ranges(rng, plan)
    work = [r["uid"] for r in ranges]
    risks = _risks(rng, work, min(max(3, params.tasks // 25), 200))
    return ProjectDataset(params, start, end_year, days, tasks, links, ranges, risks)
