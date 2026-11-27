"""Command line entry point."""

import argparse
import sys
from datetime import date
from pathlib import Path

from .check import Result, run_checks
from .generate import SIZES, Params, generate
from .io import FORMATS, read_dataset, verify_manifest, write_dataset
from .project import ProjectParams, generate_project
from .project_files import write_project
from .workforce import WorkforceParams, generate_workforce, write_workforce

MAX_SHOWN = 5


def _say(text: str) -> None:
    shown = "".join(c if c.isprintable() else ascii(c)[1:-1] for c in text)
    encoding = sys.stdout.encoding or "utf-8"
    print(shown.encode(encoding, "backslashreplace").decode(encoding))


def _folder(text: str) -> str:
    if not text.strip():
        raise argparse.ArgumentTypeError("the folder path must not be empty")
    return text


def _generate(args: argparse.Namespace) -> int:
    params = Params(
        seed=args.seed,
        months=args.months,
        size=args.size,
        anomaly_rate=args.anomaly_rate,
        start_date=args.start_date,
        background=args.background,
        budget_and_cash_flow=args.budget_and_cash_flow,
    )
    try:
        ds = generate(params)
        write_dataset(ds, Path(args.out), args.format, args.force)
    except (ValueError, OSError) as e:
        _say(f"Error: {e}")
        return 1
    rows = sum(len(t) for t in ds.tables.values())
    _say(f"Wrote {len(ds.tables)} tables ({rows} rows) to {args.out}")
    _say(f"Planted {ds.anomaly_count} anomalies, listed in labels.csv")
    if "budget_lines" in ds.tables:
        n = sum(1 for lab in ds.labels if lab["table"] == "budget_lines")
        _say(f"Planted {n} budget variances, listed in labels.csv")
    return 0


def _workforce(args: argparse.Namespace) -> int:
    params = WorkforceParams(
        seed=args.seed, staff=args.staff, days=args.days, start_date=args.start_date
    )
    try:
        ds = generate_workforce(params)
        write_workforce(ds, Path(args.out), args.force)
    except (ValueError, OSError) as e:
        _say(f"Error: {e}")
        return 1
    rows = sum(len(t) for t in ds.tables.values())
    _say(f"Wrote {len(ds.tables)} tables ({rows} rows) to {args.out}")
    return 0


def _project(args: argparse.Namespace) -> int:
    params = ProjectParams(seed=args.seed, tasks=args.tasks, start_date=args.start_date)
    try:
        ds = generate_project(params)
        write_project(ds, Path(args.out), args.force)
    except (ValueError, OSError) as e:
        _say(f"Error: {e}")
        return 1
    _say(
        f"Wrote a project with {len(ds.tasks)} tasks, {len(ds.links)} links "
        f"and {len(ds.risks)} risks to {args.out}"
    )
    return 0


def _check(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    try:
        tables, labels = read_dataset(folder)
        manifest = verify_manifest(folder)
    except (ValueError, OSError, KeyError) as e:
        _say(f"Error: {e}")
        return 1
    try:
        results = run_checks(tables, labels)
    except (ValueError, KeyError, TypeError, IndexError) as e:
        msg = f"{type(e).__name__} {e}"
        _say("Error: could not run the checks: " + ascii(msg)[1:-1][:200])
        return 1
    skipped = 0
    if not (folder / "labels.csv").exists():
        _say("SKIP labels (no labels.csv in the folder)")
        skipped += 1
    if manifest is None:
        _say("SKIP manifest (no manifest.json in the folder)")
        skipped += 1
    else:
        results.append(Result("manifest", not manifest, manifest))
    failed = False
    for r in results:
        _say(f"{'PASS' if r.ok else 'FAIL'} {r.rule}")
        for m in r.messages[:MAX_SHOWN]:
            _say(f"  {m}")
        if len(r.messages) > MAX_SHOWN:
            _say(f"  and {len(r.messages) - MAX_SHOWN} more")
        failed = failed or not r.ok
    if failed:
        _say("Some checks failed")
    elif skipped:
        _say(f"All checks passed, {skipped} skipped")
    else:
        _say("All checks passed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="synthbiz", description="Synthetic finance data."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="write a synthetic dataset")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--months", type=int, default=12)
    g.add_argument("--size", choices=sorted(SIZES), default="small")
    g.add_argument("--anomaly-rate", type=float, default=0.02)
    g.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 1))
    g.add_argument(
        "--no-background",
        dest="background",
        action="store_false",
        help="leave out the legitimate unlabeled background rows",
    )
    g.add_argument(
        "--budget-and-cash-flow",
        action="store_true",
        help="add budget_lines and fixed asset, loan and equity entries",
    )
    g.add_argument("--format", choices=FORMATS, default="csv")
    g.add_argument("--out", type=_folder, required=True)
    g.add_argument(
        "--force",
        action="store_true",
        help="replace the synthbiz files in a folder that is not empty",
    )
    g.set_defaults(func=_generate)
    w = sub.add_parser("workforce", help="write synthetic workforce tables")
    w.add_argument("--seed", type=int, default=42)
    w.add_argument("--staff", type=int, default=20)
    w.add_argument("--days", type=int, default=28)
    w.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 6, 2))
    w.add_argument("--out", type=_folder, required=True)
    w.add_argument(
        "--force",
        action="store_true",
        help="replace the synthbiz files in a folder that is not empty",
    )
    w.set_defaults(func=_workforce)
    p = sub.add_parser("project", help="write a synthetic project schedule")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tasks", type=int, default=50)
    p.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 6))
    p.add_argument("--out", type=_folder, required=True)
    p.add_argument(
        "--force",
        action="store_true",
        help="replace the synthbiz files in a folder that is not empty",
    )
    p.set_defaults(func=_project)
    c = sub.add_parser("check", help="run the tie-out checks on a dataset folder")
    c.add_argument("folder", type=_folder)
    c.set_defaults(func=_check)
    args = parser.parse_args(argv)
    code: int = args.func(args)
    return code
