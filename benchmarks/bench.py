"""Time generate and check against simple baselines.

Run from the repo root: python benchmarks/bench.py [--quick] [--repeat N]
"""

import argparse
import gc
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from benchmarks import baseline  # noqa: E402

from synthbiz import check  # noqa: E402
from synthbiz.check import run_checks  # noqa: E402
from synthbiz.generate import Params, generate  # noqa: E402

SIZES = ["small", "medium", "large"]
MONTHS = [3, 12, 36]
SEED = 42


def median_time(fn: Callable[[], Any], repeat: int) -> tuple[float, Any]:
    times: list[float] = []
    result = None
    for _ in range(repeat):
        result = None
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter()
            result = fn()
            end = time.perf_counter()
        finally:
            gc.enable()
        times.append(end - start)
    return statistics.median(times), result


def passing_rules(tables: Any, labels: list[dict[str, Any]]) -> int:
    rules: list[Callable[[], list[str]]] = [
        lambda: check.check_balanced(tables),
        lambda: check.check_subledger_ties(tables),
        lambda: check.check_bank_tie(tables),
        lambda: check.check_links(tables, labels),
        lambda: check.check_dates(tables, labels),
    ]
    count = 0
    for rule in rules:
        try:
            if not rule():
                count += 1
        except Exception:
            continue
    return count


def run_case(size: str, months: int, repeat: int) -> dict[str, Any]:
    params = Params(seed=SEED, months=months, size=size)
    gen_s, ds = median_time(lambda: generate(params), repeat)
    counts = {name: len(rows) for name, rows in ds.tables.items()}
    unlinked_s, plain = median_time(
        lambda: baseline.unlinked_rows(params, counts), repeat
    )
    new_s, new_results = median_time(lambda: run_checks(ds.tables, ds.labels), repeat)
    old_s, old_results = median_time(
        lambda: baseline.run_checks(ds.tables, ds.labels), repeat
    )
    same = [(r.rule, r.ok, r.messages) for r in new_results] == [
        (r.rule, r.ok, r.messages) for r in old_results
    ]
    return {
        "size": size,
        "months": months,
        "rows": sum(counts.values()),
        "generate_s": gen_s,
        "unlinked_s": unlinked_s,
        "check_new_s": new_s,
        "check_ref_s": old_s,
        "synthbiz_pass": sum(1 for r in new_results if r.ok),
        "unlinked_pass": passing_rules(plain, []),
        "same_as_reference": same,
    }


def table(rows: list[dict[str, Any]]) -> str:
    head = (
        "| size | months | rows | generate s | unlinked s | check s (new) "
        "| check s (reference) | synthbiz pass | unlinked pass |"
    )
    lines = [head, "|" + "---|" * 9]
    for r in rows:
        lines.append(
            f"| {r['size']} | {r['months']} | {r['rows']} "
            f"| {r['generate_s']:.4f} | {r['unlinked_s']:.4f} "
            f"| {r['check_new_s']:.4f} | {r['check_ref_s']:.4f} "
            f"| {r['synthbiz_pass']}/5 | {r['unlinked_pass']}/5 |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="small, 3 and 12 months")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--json", metavar="PATH", help="write results as JSON")
    args = parser.parse_args()
    sizes = ["small"] if args.quick else SIZES
    months = [3, 12] if args.quick else MONTHS
    print(f"Python {platform.python_version()} on {platform.machine()}")
    print(f"Seed {SEED}, median of {args.repeat} runs\n")
    rows = [run_case(s, m, args.repeat) for s in sizes for m in months]
    print(table(rows))
    if args.json:
        Path(args.json).write_text(
            json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    bad = [r for r in rows if not r["same_as_reference"]]
    for r in bad:
        print(f"MISMATCH: {r['size']} {r['months']} months", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
