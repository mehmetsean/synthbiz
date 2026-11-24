"""Rebuild the numbers block in README.md from a fresh run."""

import argparse
import hashlib
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from synthbiz.background import BACKGROUND_KINDS
from synthbiz.check import run_checks
from synthbiz.generate import Dataset, Params, generate
from synthbiz.io import read_dataset, verify_manifest, write_dataset
from synthbiz.names import FIRST_NAMES, LAST_NAMES
from synthbiz.plan import BUDGET_MIN_ACTUAL_CENTS, BUDGET_VARIANCE_RATE
from synthbiz.workforce import (
    MAX_DAYS,
    MAX_STAFF,
    WEEKDAY_SHARE,
    WEEKEND_FACTOR,
    WorkforceParams,
    generate_workforce,
    write_workforce,
)

START = "<!-- numbers:start -->"
END = "<!-- numbers:end -->"
ROOT = Path(__file__).resolve().parent.parent


def build_block() -> str:
    params = Params(seed=42, months=12, size="small", anomaly_rate=0.02)
    ds = generate(params)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        write_dataset(ds, out)
        tables, labels = read_dataset(out)
        manifest_errors = verify_manifest(out)
        digest = hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest()
    lines = ["Example: seed 42, 12 months, size small, anomaly rate 0.02.", ""]
    lines.append("Rows per table:")
    lines.append("")
    for name, rows in tables.items():
        lines.append(f"- {name}: {len(rows)}")
    lines.append(f"- labels: {len(labels)}")
    total = sum(len(r) for r in tables.values())
    lines += ["", f"Total rows: {total} (not counting labels)", ""]
    lines.append(f"Planted anomalies: {ds.anomaly_count}")
    lines.append("")
    counts = Counter(row["anomaly_type"] for row in labels)
    for kind in sorted(counts):
        lines.append(f"- {kind}: {counts[kind]}")
    lines += ["", "Background rows (legitimate, not labeled):", ""]
    bg = Counter(x["kind"] for x in ds.background)
    for kind in BACKGROUND_KINDS:
        lines.append(f"- {kind}: {bg[kind]}")
    lines += ["", "Checks:", ""]
    for r in run_checks(tables, labels):
        status = "PASS" if r.ok else f"FAIL ({len(r.messages)} findings)"
        lines.append(f"- {r.rule}: {status}")
    lines.append(f"- manifest: {'PASS' if manifest_errors == [] else 'FAIL'}")
    lines += ["", f"manifest.json sha256: {digest}"]
    lines += plan_lines()
    lines += workforce_lines()
    return "\n".join(lines)


def cash_flows(ds: Dataset) -> dict[str, int]:
    roles = {a["account_id"]: a["role"] for a in ds.tables["chart_of_accounts"]}
    types = {a["account_id"]: a["account_type"] for a in ds.tables["chart_of_accounts"]}
    entries: dict[str, list[dict[str, Any]]] = {}
    for r in ds.tables["journal_lines"]:
        entries.setdefault(r["je_id"], []).append(r)
    out = {"operating": 0, "investing": 0, "financing": 0}
    for lines in entries.values():
        cash = sum(
            r["debit_cents"] - r["credit_cents"]
            for r in lines
            if roles[r["account_id"]] == "CASH"
        )
        other = {r["account_id"] for r in lines if roles[r["account_id"]] != "CASH"}
        if any(roles[a] == "FIXED_ASSET" for a in other):
            out["investing"] += cash
        elif any(roles[a] == "LOAN" or types[a] == "EQUITY" for a in other):
            out["financing"] += cash
        else:
            out["operating"] += cash
    return out


def plan_lines() -> list[str]:
    ds = generate(Params(seed=42, months=12, budget_and_cash_flow=True))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        write_dataset(ds, out)
        tables, labels = read_dataset(out)
        manifest_errors = verify_manifest(out)
        results = run_checks(tables, labels)
    roles = {a["account_id"]: a["role"] for a in ds.tables["chart_of_accounts"]}
    held: dict[str, int] = {}
    for r in ds.tables["journal_lines"]:
        role = roles[r["account_id"]]
        net = r["debit_cents"] - r["credit_cents"]
        held[role] = held.get(role, 0) + net
    kinds = Counter(
        x["anomaly_type"] for x in ds.labels if x["table"] == "budget_lines"
    )
    lines = ["", "Budget and cash flow option: seed 42, 12 months, size small.", ""]
    lines.append(f"- budget_lines: {len(ds.tables['budget_lines'])}")
    for kind in sorted(kinds):
        lines.append(f"- {kind}: {kinds[kind]}")
    lines.append(f"- variance rate: {BUDGET_VARIANCE_RATE}")
    lines.append(f"- minimum result for a variance, cents: {BUDGET_MIN_ACTUAL_CENTS}")
    lines.append(f"- chart_of_accounts: {len(ds.tables['chart_of_accounts'])}")
    lines.append(f"- equipment at cost, cents: {held['FIXED_ASSET']}")
    lines.append(f"- accumulated depreciation, cents: {-held['ACCUM_DEPRECIATION']}")
    lines.append(f"- loan balance, cents: {-held['LOAN']}")
    lines.append(f"- owner contributions, cents: {-held['EQUITY_CONTRIBUTION']}")
    flows = cash_flows(ds)
    for name in ("operating", "investing", "financing"):
        lines.append(f"- {name} cash flow, cents: {flows[name]}")
    lines.append(f"- net change in cash, cents: {held['CASH']}")
    same = sum(flows.values()) == held["CASH"]
    lines.append(f"- cash flow identity: {'PASS' if same else 'FAIL'}")
    for r in results:
        status = "PASS" if r.ok else f"FAIL ({len(r.messages)} findings)"
        lines.append(f"- {r.rule}: {status}")
    lines.append(f"- manifest: {'PASS' if manifest_errors == [] else 'FAIL'}")
    return lines


def workforce_lines() -> list[str]:
    ds = generate_workforce(WorkforceParams(seed=42, staff=20, days=28))
    big = generate_workforce(WorkforceParams(seed=42, staff=MAX_STAFF, days=MAX_DAYS))
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a", Path(tmp) / "b"
        write_workforce(ds, a)
        write_workforce(generate_workforce(ds.params), b)
        same = all(
            (a / p.name).read_bytes() == (b / p.name).read_bytes() for p in a.iterdir()
        )
    lines = ["", "Workforce example: seed 42, 20 staff, 28 days.", ""]
    lines.append(f"- tables: {len(ds.tables)}")
    for name, rows in ds.tables.items():
        lines.append(f"- {name}: {len(rows)}")
    lines.append(f"- staff limit: 1 to {MAX_STAFF}")
    lines.append(f"- days limit: 1 to {MAX_DAYS}")
    lines.append(f"- first names: {len(FIRST_NAMES)}")
    lines.append(f"- last names: {len(LAST_NAMES)}")
    lines.append(f"- name pairs: {len(FIRST_NAMES) * len(LAST_NAMES)}")
    shares = ", ".join(f"{k} {v}" for k, v in WEEKDAY_SHARE.items())
    lines.append(f"- demand shares: {shares}")
    lines.append(f"- weekend factor: {WEEKEND_FACTOR}")
    lines.append(f"- same seed gives same bytes: {'PASS' if same else 'FAIL'}")
    lines.append(f"- availability rows, upper bound: {MAX_STAFF * MAX_DAYS}")
    measured = len(big.tables["availability"])
    lines.append(f"- availability rows, measured at the limits: {measured}")
    return lines


def replace_block(text: str, block: str) -> str:
    if START not in text or END not in text:
        raise ValueError("README.md needs the numbers start and end markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    args = parser.parse_args(argv)
    path = Path(args.readme)
    old = path.read_text(encoding="utf-8")
    new = replace_block(old, build_block())
    if args.check:
        if new != old:
            print("README numbers are out of date, run scripts/reproduce_readme.py")
            return 1
        print("README numbers match")
        return 0
    path.write_text(new, encoding="utf-8")
    print("README numbers updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
