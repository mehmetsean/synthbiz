"""Tie-out checks that run on generated tables."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from .dates import last_day_of_month
from .schema import TABLE_NAMES, schema_dict

Tables = dict[str, list[dict[str, Any]]]
Labels = list[dict[str, Any]]


@dataclass
class Result:
    rule: str
    ok: bool
    messages: list[str]


def month_ends_from_lines(lines: list[dict[str, Any]]) -> list[date]:
    if not lines:
        return []
    dates = sorted(str(r["posting_date"]) for r in lines)
    first = date.fromisoformat(dates[0])
    last = date.fromisoformat(dates[-1])
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


def _gl_balance(tables: Tables, role: str, me: str, debit_normal: bool) -> int:
    accounts = _role_accounts(tables, role)
    total = 0
    for r in tables["journal_lines"]:
        if r["account_id"] in accounts and str(r["posting_date"]) <= me:
            total += int(r["debit_cents"]) - int(r["credit_cents"])
    return total if debit_normal else -total


def check_balanced(tables: Tables) -> list[str]:
    sums: dict[str, int] = {}
    for r in tables["journal_lines"]:
        je = str(r["je_id"])
        sums[je] = sums.get(je, 0) + int(r["debit_cents"]) - int(r["credit_cents"])
    return [
        f"{je}: debits minus credits is {diff} cents"
        for je, diff in sorted(sums.items())
        if diff != 0
    ]


def _open_balance(
    invoices: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    inv_date: str,
    set_date: str,
    me: str,
) -> int:
    billed = sum(int(r["amount_cents"]) for r in invoices if str(r[inv_date]) <= me)
    settled = sum(int(r["amount_cents"]) for r in settlements if str(r[set_date]) <= me)
    return billed - settled


def check_subledger_ties(tables: Tables) -> list[str]:
    errors: list[str] = []
    for me in month_ends_from_lines(tables["journal_lines"]):
        s = me.isoformat()
        ap_sub = _open_balance(
            tables["ap_invoices"],
            tables["ap_payments"],
            "invoice_date",
            "payment_date",
            s,
        )
        ap_gl = _gl_balance(tables, "AP_CONTROL", s, debit_normal=False)
        if ap_sub != ap_gl:
            errors.append(f"AP {s}: subledger {ap_sub} vs control {ap_gl} cents")
        ar_sub = _open_balance(
            tables["ar_invoices"],
            tables["ar_receipts"],
            "invoice_date",
            "receipt_date",
            s,
        )
        ar_gl = _gl_balance(tables, "AR_CONTROL", s, debit_normal=True)
        if ar_sub != ar_gl:
            errors.append(f"AR {s}: subledger {ar_sub} vs control {ar_gl} cents")
    return errors


def reconciling_items(tables: Tables, ends: list[date]) -> list[dict[str, Any]]:
    """Items posted to GL cash by a month end but not yet on the bank statement."""
    gl_dates: dict[str, tuple[str, str]] = {}
    for p in tables["ap_payments"]:
        gl_dates[str(p["payment_id"])] = ("AP_PAYMENT", str(p["payment_date"]))
    for r in tables["ar_receipts"]:
        gl_dates[str(r["receipt_id"])] = ("AR_RECEIPT", str(r["receipt_date"]))
    out: list[dict[str, Any]] = []
    for me in ends:
        s = me.isoformat()
        for b in tables["bank_transactions"]:
            ref = gl_dates.get(str(b["ref_id"]))
            if ref is None or str(b["ref_type"]) != ref[0]:
                continue
            if ref[1] <= s < str(b["bank_date"]):
                amount = int(b["amount_cents"])
                out.append(
                    {
                        "month_end": s,
                        "item_type": (
                            "OUTSTANDING_PAYMENT"
                            if amount < 0
                            else "DEPOSIT_IN_TRANSIT"
                        ),
                        "ref_type": ref[0],
                        "ref_id": str(b["ref_id"]),
                        "gl_date": ref[1],
                        "bank_date": str(b["bank_date"]),
                        "amount_cents": amount,
                    }
                )
    out.sort(key=lambda i: (i["month_end"], i["ref_id"]))
    return out


def check_bank_tie(tables: Tables) -> list[str]:
    errors: list[str] = []
    ends = month_ends_from_lines(tables["journal_lines"])
    items = reconciling_items(tables, ends)
    for me in ends:
        s = me.isoformat()
        bank = sum(
            int(b["amount_cents"])
            for b in tables["bank_transactions"]
            if str(b["bank_date"]) <= s
        )
        adjust = sum(int(i["amount_cents"]) for i in items if i["month_end"] == s)
        gl = _gl_balance(tables, "CASH", s, debit_normal=True)
        if bank + adjust != gl:
            errors.append(
                f"Bank {s}: bank {bank} + reconciling items {adjust} "
                f"vs GL cash {gl} cents"
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
    for name in TABLE_NAMES:
        key = schema[name]["primary_key"][0]
        for col, target in schema[name]["foreign_keys"].items():
            other, other_col = target.split(".")
            have = {str(r[other_col]) for r in tables[other]}
            for r in tables[name]:
                if str(r[col]) not in have:
                    errors.append(f"{name} {r[key]}: {col} {r[col]} not in {other}")
    refs = {str(r["payment_id"]) for r in tables["ap_payments"]}
    refs |= {str(r["receipt_id"]) for r in tables["ar_receipts"]}
    refs |= {str(r["je_id"]) for r in tables["journal_lines"]}
    for b in tables["bank_transactions"]:
        if str(b["ref_id"]) not in refs:
            errors.append(
                f"bank_transactions {b['bank_txn_id']}: ref {b['ref_id']} not found"
            )
    for lab in labels or []:
        table = str(lab["table"])
        if table not in schema or table == "labels":
            errors.append(f"labels: unknown table {table}")
            continue
        key = schema[table]["primary_key"][0]
        if str(lab["row_id"]) not in {str(r[key]) for r in tables[table]}:
            errors.append(f"labels: {table} {lab['row_id']} not found")
    return errors


def _later_than_invoice(
    tables: Tables, name: str, key: str, day: str, invoices: str
) -> list[str]:
    inv_dates = {str(r["invoice_id"]): str(r["invoice_date"]) for r in tables[invoices]}
    out: list[str] = []
    for r in tables[name]:
        inv = inv_dates.get(str(r["invoice_id"]))
        if inv is not None and str(r[day]) < inv:
            out.append(f"{name} {r[key]}: {day} {r[day]} is before invoice date {inv}")
    return out


def check_dates(tables: Tables, labels: Labels) -> list[str]:
    errors: list[str] = []
    for name in ("ap_invoices", "ar_invoices"):
        for r in tables[name]:
            if str(r["due_date"]) < str(r["invoice_date"]):
                errors.append(
                    f"{name} {r['invoice_id']}: due date {r['due_date']} "
                    f"is before invoice date {r['invoice_date']}"
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
                f"journal_lines {r['line_id']}: period {r['period']} does not match "
                f"posting date {r['posting_date']} and is not a labeled anomaly"
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
