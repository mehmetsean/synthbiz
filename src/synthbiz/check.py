"""Tie-out checks that run on generated tables."""

from bisect import bisect_left
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from .dates import last_day_of_month
from .schema import TABLE_NAMES, schema_dict

MAX_MONTHS = 1200
MAX_RECONCILING_ITEMS = 1_000_000

Tables = dict[str, list[dict[str, Any]]]
Labels = list[dict[str, Any]]


def _safe(value: object) -> str:
    """Escape control and non-ASCII characters and cut long values."""
    return ascii(str(value))[1:-1][:80]


@dataclass
class Result:
    rule: str
    ok: bool
    messages: list[str]


def month_ends_from_lines(lines: list[dict[str, Any]]) -> list[date]:
    if not lines:
        return []
    dates = [str(r["posting_date"]) for r in lines]
    first = date.fromisoformat(min(dates))
    last = date.fromisoformat(max(dates))
    span = (last.year - first.year) * 12 + last.month - first.month + 1
    if span > MAX_MONTHS:
        raise ValueError(
            f"journal_lines span {span} months; check handles at most {MAX_MONTHS}"
        )
    out: list[date] = []
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(last_day_of_month(y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _role_accounts(tables: Tables, role: str) -> set[str]:
    return {
        str(a["account_id"]) for a in tables["chart_of_accounts"] if a["role"] == role
    }


def _balances(
    ends: list[str],
    rows: Iterable[tuple[str, dict[str, Any]]],
    amount: Callable[[dict[str, Any]], int],
) -> list[int]:
    """Running total at each month end, from (date, row) pairs."""
    if not ends:
        return []
    sums = [0] * len(ends)
    for day, row in rows:
        i = bisect_left(ends, day)
        if i < len(ends):
            sums[i] += amount(row)
    total = 0
    for i, value in enumerate(sums):
        total += value
        sums[i] = total
    return sums


def _net(row: dict[str, Any]) -> int:
    return int(row["debit_cents"]) - int(row["credit_cents"])


def _cents(row: dict[str, Any]) -> int:
    return int(row["amount_cents"])


def _gl_balances(
    tables: Tables, ends: list[str], roles: dict[str, bool]
) -> dict[str, list[int]]:
    """GL balance at each month end per role. The flag marks debit-normal roles."""
    if not ends:
        return {role: [] for role in roles}
    out: dict[str, list[int]] = {}
    for role, debit_normal in roles.items():
        ids = _role_accounts(tables, role)
        rows = (
            (str(r["posting_date"]), r)
            for r in tables["journal_lines"]
            if r["account_id"] in ids
        )
        totals = _balances(ends, rows, _net)
        out[role] = totals if debit_normal else [-t for t in totals]
    return out


def check_balanced(tables: Tables) -> list[str]:
    sums: dict[str, int] = {}
    for r in tables["journal_lines"]:
        je = str(r["je_id"])
        sums[je] = sums.get(je, 0) + int(r["debit_cents"]) - int(r["credit_cents"])
    return [
        f"{_safe(je)}: debits minus credits is {diff} cents"
        for je, diff in sorted(sums.items())
        if diff != 0
    ]


def _open_balances(
    invoices: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    inv_date: str,
    set_date: str,
    ends: list[str],
) -> list[int]:
    billed = _balances(ends, ((str(r[inv_date]), r) for r in invoices), _cents)
    settled = _balances(ends, ((str(r[set_date]), r) for r in settlements), _cents)
    return [x - y for x, y in zip(billed, settled, strict=True)]


def check_subledger_ties(tables: Tables) -> list[str]:
    errors: list[str] = []
    ends = [me.isoformat() for me in month_ends_from_lines(tables["journal_lines"])]
    gl = _gl_balances(tables, ends, {"AP_CONTROL": False, "AR_CONTROL": True})
    ap_sub = _open_balances(
        tables["ap_invoices"],
        tables["ap_payments"],
        "invoice_date",
        "payment_date",
        ends,
    )
    ar_sub = _open_balances(
        tables["ar_invoices"],
        tables["ar_receipts"],
        "invoice_date",
        "receipt_date",
        ends,
    )
    for i, s in enumerate(ends):
        ap_gl = gl["AP_CONTROL"][i]
        if ap_sub[i] != ap_gl:
            errors.append(f"AP {s}: subledger {ap_sub[i]} vs control {ap_gl} cents")
        ar_gl = gl["AR_CONTROL"][i]
        if ar_sub[i] != ar_gl:
            errors.append(f"AR {s}: subledger {ar_sub[i]} vs control {ar_gl} cents")
    return errors


def reconciling_items(tables: Tables, ends: list[date]) -> list[dict[str, Any]]:
    """Items posted to GL cash by a month end but not yet on the bank statement."""
    gl_dates: dict[str, tuple[str, str]] = {}
    for p in tables["ap_payments"]:
        gl_dates[str(p["payment_id"])] = ("AP_PAYMENT", str(p["payment_date"]))
    for r in tables["ar_receipts"]:
        gl_dates[str(r["receipt_id"])] = ("AR_RECEIPT", str(r["receipt_date"]))
    names = sorted(me.isoformat() for me in ends)
    if not names:
        return []
    per_end: list[list[dict[str, Any]]] = [[] for _ in names]
    count = 0
    for b in tables["bank_transactions"]:
        ref = gl_dates.get(str(b["ref_id"]))
        if ref is None or str(b["ref_type"]) != ref[0]:
            continue
        bank_date = str(b["bank_date"])
        window = range(bisect_left(names, ref[1]), bisect_left(names, bank_date))
        if not window:
            continue
        count += len(window)
        if count > MAX_RECONCILING_ITEMS:
            raise ValueError(
                f"more than {MAX_RECONCILING_ITEMS} reconciling items; "
                "check the bank and GL dates"
            )
        amount = int(b["amount_cents"])
        kind = "OUTSTANDING_PAYMENT" if amount < 0 else "DEPOSIT_IN_TRANSIT"
        for i in window:
            per_end[i].append(
                {
                    "month_end": names[i],
                    "item_type": kind,
                    "ref_type": ref[0],
                    "ref_id": str(b["ref_id"]),
                    "gl_date": ref[1],
                    "bank_date": bank_date,
                    "amount_cents": amount,
                }
            )
    out = [item for group in per_end for item in group]
    out.sort(key=lambda i: (i["month_end"], i["ref_id"]))
    return out


def check_bank_tie(tables: Tables) -> list[str]:
    errors: list[str] = []
    ends = month_ends_from_lines(tables["journal_lines"])
    items = reconciling_items(tables, ends)
    names = [me.isoformat() for me in ends]
    banks = _balances(
        names, ((str(b["bank_date"]), b) for b in tables["bank_transactions"]), _cents
    )
    adjusts: dict[str, int] = {}
    for i in items:
        adjusts[i["month_end"]] = adjusts.get(i["month_end"], 0) + int(
            i["amount_cents"]
        )
    cash = _gl_balances(tables, names, {"CASH": True})["CASH"]
    for k, s in enumerate(names):
        adjust = adjusts.get(s, 0)
        if banks[k] + adjust != cash[k]:
            errors.append(
                f"Bank {s}: bank {banks[k]} + reconciling items {adjust} "
                f"vs GL cash {cash[k]} cents"
            )
    listed = tables.get("reconciling_items")
    if listed is not None:
        keys = ["month_end", "item_type", "ref_type", "ref_id", "gl_date", "bank_date"]
        want = [[str(i[k]) for k in keys] + [int(i["amount_cents"])] for i in items]
        have = [[str(i[k]) for k in keys] + [int(i["amount_cents"])] for i in listed]
        if want != have:
            errors.append("reconciling_items does not match the bank and GL dates")
    return errors


def check_links(tables: Tables, labels: Labels | None = None) -> list[str]:
    errors: list[str] = []
    schema = schema_dict()["tables"]
    cache: dict[tuple[str, str], set[str]] = {}

    def values(table: str, col: str) -> set[str]:
        if (table, col) not in cache:
            cache[(table, col)] = {str(r[col]) for r in tables[table]}
        return cache[(table, col)]

    for name in TABLE_NAMES:
        key = schema[name]["primary_key"][0]
        for col, target in schema[name]["foreign_keys"].items():
            other, other_col = target.split(".")
            have = values(other, other_col)
            for r in tables[name]:
                if str(r[col]) not in have:
                    errors.append(
                        f"{name} {_safe(r[key])}: {col} {_safe(r[col])} not in {other}"
                    )
    refs = {str(r["payment_id"]) for r in tables["ap_payments"]}
    refs |= {str(r["receipt_id"]) for r in tables["ar_receipts"]}
    refs |= {str(r["je_id"]) for r in tables["journal_lines"]}
    for b in tables["bank_transactions"]:
        if str(b["ref_id"]) not in refs:
            errors.append(
                f"bank_transactions {_safe(b['bank_txn_id'])}: "
                f"ref {_safe(b['ref_id'])} not found"
            )
    for lab in labels or []:
        table = str(lab["table"])
        if table not in schema or table == "labels":
            errors.append(f"labels: unknown table {_safe(table)}")
            continue
        key = schema[table]["primary_key"][0]
        if str(lab["row_id"]) not in values(table, key):
            errors.append(f"labels: {table} {_safe(lab['row_id'])} not found")
    return errors


def _later_than_invoice(
    tables: Tables, name: str, key: str, day: str, invoices: str
) -> list[str]:
    inv_dates = {str(r["invoice_id"]): str(r["invoice_date"]) for r in tables[invoices]}
    out: list[str] = []
    for r in tables[name]:
        inv = inv_dates.get(str(r["invoice_id"]))
        if inv is not None and str(r[day]) < inv:
            out.append(
                f"{name} {_safe(r[key])}: {day} {_safe(r[day])} "
                f"is before invoice date {_safe(inv)}"
            )
    return out


def check_dates(tables: Tables, labels: Labels) -> list[str]:
    errors: list[str] = []
    for name in ("ap_invoices", "ar_invoices"):
        for r in tables[name]:
            if str(r["due_date"]) < str(r["invoice_date"]):
                errors.append(
                    f"{name} {_safe(r['invoice_id'])}: due date {_safe(r['due_date'])} "
                    f"is before invoice date {_safe(r['invoice_date'])}"
                )
    errors += _later_than_invoice(
        tables, "ap_payments", "payment_id", "payment_date", "ap_invoices"
    )
    errors += _later_than_invoice(
        tables, "ar_receipts", "receipt_id", "receipt_date", "ar_invoices"
    )
    planted = {
        str(lab["row_id"])
        for lab in labels
        if lab["table"] == "journal_lines"
        and lab["anomaly_type"] == "out_of_period_entry"
    }
    planted_jes = {
        str(r["je_id"]) for r in tables["journal_lines"] if str(r["line_id"]) in planted
    }
    for r in tables["journal_lines"]:
        month = str(r["posting_date"])[:7]
        if str(r["period"]) != month and str(r["je_id"]) not in planted_jes:
            errors.append(
                f"journal_lines {_safe(r['line_id'])}: period {_safe(r['period'])} "
                f"does not match posting date {_safe(r['posting_date'])} "
                "and is not a labeled anomaly"
            )
    return errors


def run_checks(tables: Tables, labels: Labels) -> list[Result]:
    """Run every rule. Labels mark planted out-of-period entries."""
    found = [
        ("balanced_entries", check_balanced(tables)),
        ("ap_ar_subledger_ties", check_subledger_ties(tables)),
        ("bank_ties_to_gl_cash", check_bank_tie(tables)),
        ("links", check_links(tables, labels)),
        ("dates", check_dates(tables, labels)),
    ]
    return [Result(name, not errs, errs) for name, errs in found]
