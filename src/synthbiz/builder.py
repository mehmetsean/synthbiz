"""Builds linked rows and posts them to the ledger."""

import random
from datetime import date, timedelta
from typing import Any

from .dates import add_business_days

Row = dict[str, Any]

APPROVAL_LIMIT_CENTS = 500_000

CASH = "1000"
AR = "1100"
AP = "2000"
ACCRUED = "2100"
EQUITY = "3000"
SALES = "4000"

CHART: list[tuple[str, str, str, str, str]] = [
    (CASH, "Operating Cash", "ASSET", "DEBIT", "CASH"),
    (AR, "Accounts Receivable", "ASSET", "DEBIT", "AR_CONTROL"),
    (AP, "Accounts Payable", "LIABILITY", "CREDIT", "AP_CONTROL"),
    (ACCRUED, "Accrued Liabilities", "LIABILITY", "CREDIT", ""),
    (EQUITY, "Owner Equity", "EQUITY", "CREDIT", ""),
    (SALES, "Product Sales", "REVENUE", "CREDIT", ""),
    ("5000", "Raw Materials", "EXPENSE", "DEBIT", ""),
    ("5100", "Freight In", "EXPENSE", "DEBIT", ""),
    ("6100", "Utilities", "EXPENSE", "DEBIT", ""),
    ("6200", "Contract Services", "EXPENSE", "DEBIT", ""),
    ("6900", "Miscellaneous Expense", "EXPENSE", "DEBIT", ""),
]

CATEGORIES: list[tuple[str, str]] = [
    ("Materials", "5000"),
    ("Freight", "5100"),
    ("Utilities", "6100"),
    ("Services", "6200"),
]


def nonround(cents: int) -> int:
    """Avoid amounts that are a multiple of 100 dollars."""
    return cents + 17 if cents % 10_000 == 0 else cents


class Builder:
    def __init__(self, seed: int, start: date, end: date) -> None:
        self.rng = random.Random(seed)
        self.start = start
        self.end = end
        self.tables: dict[str, list[Row]] = {}
        self.labels: list[dict[str, str]] = []
        self._counters: dict[str, int] = {}
        self.base_vendors = 0

    def table(self, name: str) -> list[Row]:
        return self.tables.setdefault(name, [])

    def next_id(self, prefix: str, width: int = 6) -> str:
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        return f"{prefix}-{n:0{width}d}"

    def label(self, table: str, row_id: str, kind: str, details: str) -> None:
        self.labels.append(
            {"table": table, "row_id": row_id, "anomaly_type": kind, "details": details}
        )

    def post(
        self,
        d: date,
        lines: list[tuple[str, int, int]],
        memo: str,
        source_type: str,
        source_id: str,
        created_by: str,
        approved_by: str,
        period: str | None = None,
    ) -> tuple[str, str]:
        """Post one entry. Returns the entry id and its first line id."""
        je_id = self.next_id("JE")
        first = ""
        for n, (account, debit, credit) in enumerate(lines, start=1):
            line_id = self.next_id("JL", 7)
            first = first or line_id
            self.table("journal_lines").append(
                {
                    "line_id": line_id,
                    "je_id": je_id,
                    "line_no": n,
                    "posting_date": d.isoformat(),
                    "period": period or d.isoformat()[:7],
                    "account_id": account,
                    "debit_cents": debit,
                    "credit_cents": credit,
                    "memo": memo,
                    "source_type": source_type,
                    "source_id": source_id,
                    "created_by": created_by,
                    "approved_by": approved_by,
                }
            )
        return je_id, first

    def clear_bank(
        self, ref_type: str, ref_id: str, gl_date: date, amount: int
    ) -> None:
        lag = self.rng.randint(1, 4 if ref_type == "AP_PAYMENT" else 3)
        self.table("bank_transactions").append(
            {
                "bank_txn_id": self.next_id("BK"),
                "bank_date": add_business_days(
                    gl_date + timedelta(days=1), lag - 1
                ).isoformat(),
                "amount_cents": amount,
                "ref_type": ref_type,
                "ref_id": ref_id,
            }
        )

    def ap_invoice(
        self, d: date, vendor: Row, amount: int, number: str | None = None
    ) -> Row:
        rng = self.rng
        invoice_id = self.next_id("API")
        account = dict(CATEGORIES)[vendor["category"]]
        approver = (
            "AP_MANAGER_1" if amount >= APPROVAL_LIMIT_CENTS else "AP_SUPERVISOR_1"
        )
        creator = rng.choice(["AP_CLERK_1", "AP_CLERK_2"])
        je_id, _ = self.post(
            d,
            [(account, amount, 0), (AP, 0, amount)],
            f"Vendor invoice {invoice_id}",
            "AP_INVOICE",
            invoice_id,
            creator,
            approver,
        )
        row: Row = {
            "invoice_id": invoice_id,
            "vendor_id": vendor["vendor_id"],
            "invoice_number": number or str(rng.randint(10000, 99999)),
            "invoice_date": d.isoformat(),
            "due_date": (d + timedelta(days=vendor["terms_days"])).isoformat(),
            "amount_cents": amount,
            "expense_account_id": account,
            "je_id": je_id,
            "created_by": creator,
            "approved_by": approver,
        }
        self.table("ap_invoices").append(row)
        return row

    def ap_payment(self, invoice: Row, d: date) -> Row:
        payment_id = self.next_id("APP")
        amount = invoice["amount_cents"]
        je_id, _ = self.post(
            d,
            [(AP, amount, 0), (CASH, 0, amount)],
            f"Payment {payment_id}",
            "AP_PAYMENT",
            payment_id,
            "AP_CLERK_1",
            "AP_MANAGER_1",
        )
        row: Row = {
            "payment_id": payment_id,
            "vendor_id": invoice["vendor_id"],
            "invoice_id": invoice["invoice_id"],
            "payment_date": d.isoformat(),
            "amount_cents": amount,
            "method": self.rng.choice(["ACH", "CHECK"]),
            "je_id": je_id,
            "created_by": "AP_CLERK_1",
            "approved_by": "AP_MANAGER_1",
        }
        self.table("ap_payments").append(row)
        self.clear_bank("AP_PAYMENT", payment_id, d, -amount)
        return row

    def ar_invoice(self, d: date, customer: Row, amount: int) -> Row:
        invoice_id = self.next_id("ARI")
        je_id, _ = self.post(
            d,
            [(AR, amount, 0), (SALES, 0, amount)],
            f"Customer invoice {invoice_id}",
            "AR_INVOICE",
            invoice_id,
            "AR_CLERK_1",
            "AR_MANAGER_1",
        )
        row: Row = {
            "invoice_id": invoice_id,
            "customer_id": customer["customer_id"],
            "invoice_number": f"SI-{invoice_id[-6:]}",
            "invoice_date": d.isoformat(),
            "due_date": (d + timedelta(days=customer["terms_days"])).isoformat(),
            "amount_cents": amount,
            "je_id": je_id,
            "created_by": "AR_CLERK_1",
        }
        self.table("ar_invoices").append(row)
        return row

    def ar_receipt(self, invoice: Row, d: date) -> Row:
        receipt_id = self.next_id("ARR")
        amount = invoice["amount_cents"]
        je_id, _ = self.post(
            d,
            [(CASH, amount, 0), (AR, 0, amount)],
            f"Receipt {receipt_id}",
            "AR_RECEIPT",
            receipt_id,
            "AR_CLERK_1",
            "AR_MANAGER_1",
        )
        row: Row = {
            "receipt_id": receipt_id,
            "customer_id": invoice["customer_id"],
            "invoice_id": invoice["invoice_id"],
            "receipt_date": d.isoformat(),
            "amount_cents": amount,
            "je_id": je_id,
            "created_by": "AR_CLERK_1",
        }
        self.table("ar_receipts").append(row)
        self.clear_bank("AR_RECEIPT", receipt_id, d, amount)
        return row

    def manual_entry(
        self,
        d: date,
        amount: int,
        account: str = "6900",
        created_by: str | None = None,
        approved_by: str | None = "CONTROLLER_1",
        period: str | None = None,
        memo: str = "Accrual",
    ) -> tuple[str, str]:
        creator = created_by or self.rng.choice(["GL_ACCOUNTANT_1", "GL_ACCOUNTANT_2"])
        return self.post(
            d,
            [(account, amount, 0), (ACCRUED, 0, amount)],
            memo,
            "MANUAL",
            "",
            creator,
            approved_by or "",
            period,
        )
