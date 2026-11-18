"""Table definitions: columns, types, keys and descriptions."""

from typing import Any

Col = tuple[str, str, str]

DISCLAIMER = "Synthetic data for testing and learning only. Any match with a real business is unintended. Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance."
LABEL_COLUMNS = ["table", "row_id", "anomaly_type", "details"]

_TABLES: dict[str, dict[str, Any]] = {
    "chart_of_accounts": {
        "description": "Ledger accounts. The role column marks control and cash accounts.",
        "primary_key": ["account_id"],
        "foreign_keys": {},
        "columns": [
            ("account_id", "string", "Account number."),
            ("account_name", "string", "Account name."),
            ("account_type", "string", "ASSET, LIABILITY, EQUITY, REVENUE or EXPENSE."),
            ("normal_balance", "string", "DEBIT or CREDIT."),
            ("role", "string", "CASH, AP_CONTROL, AR_CONTROL or empty."),
        ],
    },
    "journal_lines": {
        "description": "One row per journal line. Lines with the same je_id form one entry.",
        "primary_key": ["line_id"],
        "foreign_keys": {"account_id": "chart_of_accounts.account_id"},
        "columns": [
            ("line_id", "string", "Line id."),
            ("je_id", "string", "Journal entry id."),
            ("line_no", "integer", "Line number within the entry."),
            ("posting_date", "date", "Date the entry was posted."),
            ("period", "string", "Accounting period, YYYY-MM."),
            ("account_id", "string", "Account posted to."),
            ("debit_cents", "integer", "Debit amount in cents."),
            ("credit_cents", "integer", "Credit amount in cents."),
            ("memo", "string", "Short description."),
            (
                "source_type",
                "string",
                "OPENING, AP_INVOICE, AP_PAYMENT, AR_INVOICE, AR_RECEIPT or MANUAL.",
            ),
            (
                "source_id",
                "string",
                "Id of the subledger row that posted here, empty for manual entries.",
            ),
            ("created_by", "string", "Role id of the poster."),
            ("approved_by", "string", "Role id of the approver, empty if none."),
        ],
    },
    "vendors": {
        "description": "Vendor master.",
        "primary_key": ["vendor_id"],
        "foreign_keys": {},
        "columns": [
            ("vendor_id", "string", "Vendor id."),
            ("vendor_name", "string", "Vendor name."),
            ("category", "string", "Spend category."),
            ("terms_days", "integer", "Payment terms in days."),
        ],
    },
    "ap_invoices": {
        "description": "Vendor invoices. Each posts to one journal entry.",
        "primary_key": ["invoice_id"],
        "foreign_keys": {
            "vendor_id": "vendors.vendor_id",
            "expense_account_id": "chart_of_accounts.account_id",
            "je_id": "journal_lines.je_id",
        },
        "columns": [
            ("invoice_id", "string", "Invoice id."),
            ("vendor_id", "string", "Vendor."),
            ("invoice_number", "string", "Number printed on the vendor invoice."),
            ("invoice_date", "date", "Invoice and posting date."),
            ("due_date", "date", "Due date."),
            ("amount_cents", "integer", "Invoice total in cents."),
            ("expense_account_id", "string", "Debit account."),
            ("je_id", "string", "Journal entry it posted to."),
            ("created_by", "string", "Role id that entered it."),
            ("approved_by", "string", "Role id that approved it."),
        ],
    },
    "ap_payments": {
        "description": "Payments to vendors. Each posts to one journal entry.",
        "primary_key": ["payment_id"],
        "foreign_keys": {
            "vendor_id": "vendors.vendor_id",
            "invoice_id": "ap_invoices.invoice_id",
            "je_id": "journal_lines.je_id",
        },
        "columns": [
            ("payment_id", "string", "Payment id."),
            ("vendor_id", "string", "Vendor paid."),
            ("invoice_id", "string", "Invoice paid."),
            ("payment_date", "date", "Payment and posting date."),
            ("amount_cents", "integer", "Amount paid in cents."),
            ("method", "string", "ACH or CHECK."),
            ("je_id", "string", "Journal entry it posted to."),
            ("created_by", "string", "Role id that entered it."),
            ("approved_by", "string", "Role id that approved it."),
        ],
    },
    "customers": {
        "description": "Customer master.",
        "primary_key": ["customer_id"],
        "foreign_keys": {},
        "columns": [
            ("customer_id", "string", "Customer id."),
            ("customer_name", "string", "Customer name."),
            ("terms_days", "integer", "Payment terms in days."),
        ],
    },
    "ar_invoices": {
        "description": "Customer invoices. Each posts to one journal entry.",
        "primary_key": ["invoice_id"],
        "foreign_keys": {
            "customer_id": "customers.customer_id",
            "je_id": "journal_lines.je_id",
        },
        "columns": [
            ("invoice_id", "string", "Invoice id."),
            ("customer_id", "string", "Customer billed."),
            ("invoice_number", "string", "Invoice number."),
            ("invoice_date", "date", "Invoice and posting date."),
            ("due_date", "date", "Due date."),
            ("amount_cents", "integer", "Invoice total in cents."),
            ("je_id", "string", "Journal entry it posted to."),
            ("created_by", "string", "Role id that entered it."),
        ],
    },
    "ar_receipts": {
        "description": "Customer receipts. Each posts to one journal entry.",
        "primary_key": ["receipt_id"],
        "foreign_keys": {
            "customer_id": "customers.customer_id",
            "invoice_id": "ar_invoices.invoice_id",
            "je_id": "journal_lines.je_id",
        },
        "columns": [
            ("receipt_id", "string", "Receipt id."),
            ("customer_id", "string", "Customer paying."),
            ("invoice_id", "string", "Invoice paid."),
            ("receipt_date", "date", "Receipt and posting date."),
            ("amount_cents", "integer", "Amount received in cents."),
            ("je_id", "string", "Journal entry it posted to."),
            ("created_by", "string", "Role id that entered it."),
        ],
    },
    "bank_transactions": {
        "description": "Bank statement lines. Each clears one payment or receipt, a few business days after its GL date.",
        "primary_key": ["bank_txn_id"],
        "foreign_keys": {},
        "columns": [
            ("bank_txn_id", "string", "Bank line id."),
            ("bank_date", "date", "Date the item cleared the bank."),
            (
                "amount_cents",
                "integer",
                "Signed amount in cents, negative for money out.",
            ),
            ("ref_type", "string", "AP_PAYMENT, AR_RECEIPT or OPENING."),
            (
                "ref_id",
                "string",
                "Id of the payment or receipt it clears. For OPENING, the journal entry id.",
            ),
        ],
    },
    "reconciling_items": {
        "description": "Items in the GL cash balance but not yet on the bank statement at a month end.",
        "primary_key": ["month_end", "ref_id"],
        "foreign_keys": {},
        "columns": [
            ("month_end", "date", "Month end the item belongs to."),
            ("item_type", "string", "OUTSTANDING_PAYMENT or DEPOSIT_IN_TRANSIT."),
            ("ref_type", "string", "AP_PAYMENT or AR_RECEIPT."),
            ("ref_id", "string", "Payment or receipt id."),
            ("gl_date", "date", "Date posted to the GL."),
            ("bank_date", "date", "Date it cleared the bank."),
            ("amount_cents", "integer", "Signed effect on GL cash in cents."),
        ],
    },
}

TABLE_NAMES = list(_TABLES)


def columns(table: str) -> list[str]:
    return [c[0] for c in _TABLES[table]["columns"]]


def money_columns(table: str) -> list[str]:
    cols = _TABLES[table]["columns"]
    return [n for n, ty, _ in cols if ty == "integer" and n.endswith("_cents")]


def schema_dict() -> dict[str, Any]:
    tables: dict[str, Any] = {}
    for name, t in _TABLES.items():
        tables[name] = {
            "description": t["description"],
            "primary_key": t["primary_key"],
            "foreign_keys": t["foreign_keys"],
            "columns": [
                {"name": n, "type": ty, "description": d} for n, ty, d in t["columns"]
            ],
        }
    tables["labels"] = {
        "description": (
            "One row per injected anomaly. Journal anomalies point to the first"
            " line of the entry; every line with the same je_id is part of it."
            " A split_invoice label points to the first invoice of the group and"
            " lists the others in details."
        ),
        "primary_key": ["table", "row_id", "anomaly_type"],
        "foreign_keys": {},
        "columns": [
            {
                "name": "table",
                "type": "string",
                "description": "Table holding the row.",
            },
            {
                "name": "row_id",
                "type": "string",
                "description": "Primary key of the labeled row.",
            },
            {
                "name": "anomaly_type",
                "type": "string",
                "description": "Kind of anomaly.",
            },
            {
                "name": "details",
                "type": "string",
                "description": "Short plain description.",
            },
        ],
    }
    return {
        "synthetic": True,
        "amounts": "All amounts are integer cents.",
        "tables": tables,
    }


def data_dictionary(schema: dict[str, Any]) -> str:
    lines = [
        "# Data dictionary",
        "",
        DISCLAIMER,
        "",
        schema["amounts"],
        "",
    ]
    for name, t in schema["tables"].items():
        lines += [f"## {name}", "", t["description"], ""]
        lines.append(f"Primary key: {', '.join(t['primary_key'])}")
        for col, target in t["foreign_keys"].items():
            lines.append(f"Foreign key: {col} to {target}")
        lines += ["", "| Column | Type | Description |", "| --- | --- | --- |"]
        for c in t["columns"]:
            lines.append(f"| `{c['name']}` | {c['type']} | {c['description']} |")
        lines.append("")
    return "\n".join(lines)
