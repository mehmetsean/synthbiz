"""Command line entry point."""

import argparse
from datetime import date
from pathlib import Path

from .check import Result, run_checks
from .generate import SIZES, Params, generate
from .io import FORMATS, read_dataset, verify_manifest, write_dataset

MAX_SHOWN = 5


def _generate(args: argparse.Namespace) -> int:
    params = Params(
        seed=args.seed,
        months=args.months,
        size=args.size,
        anomaly_rate=args.anomaly_rate,
        start_date=args.start_date,
    )
    try:
        ds = generate(params)
        write_dataset(ds, Path(args.out), args.format, args.force)
    except (ValueError, OSError) as e:
        print(f"Error: {e}")
        return 1
    rows = sum(len(t) for t in ds.tables.values())
    print(f"Wrote {len(ds.tables)} tables ({rows} rows) to {args.out}")
    print(f"Planted {ds.anomaly_count} anomalies, listed in labels.csv")
    return 0


def _check(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    try:
        tables, labels = read_dataset(folder)
    except (ValueError, OSError, KeyError) as e:
        print(f"Error: {e}")
        return 1
    results = run_checks(tables, labels)
    manifest = verify_manifest(folder)
    if manifest is None:
        print("SKIP manifest (no manifest.json in the folder)")
    else:
        results.append(Result("manifest", not manifest, manifest))
    failed = False
    for r in results:
        print(f"{'PASS' if r.ok else 'FAIL'} {r.rule}")
        for m in r.messages[:MAX_SHOWN]:
            print(f"  {m}")
        if len(r.messages) > MAX_SHOWN:
            print(f"  and {len(r.messages) - MAX_SHOWN} more")
        failed = failed or not r.ok
    print("Some checks failed" if failed else "All checks passed")
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
    g.add_argument("--format", choices=FORMATS, default="csv")
    g.add_argument("--out", required=True)
    g.add_argument(
        "--force",
        action="store_true",
        help="replace the synthbiz files in a folder that is not empty",
    )
    g.set_defaults(func=_generate)
    c = sub.add_parser("check", help="run the tie-out checks on a dataset folder")
    c.add_argument("folder")
    c.set_defaults(func=_check)
    args = parser.parse_args(argv)
    code: int = args.func(args)
    return code
