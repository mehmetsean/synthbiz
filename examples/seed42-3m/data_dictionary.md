# Data dictionary

Synthetic data from synthbiz. Any match with a real business is unintended.
For testing and learning only. Decision support only, not legal, tax,
accounting or assurance advice. No guarantee of compliance.

All amounts are integer cents.

## chart_of_accounts

Ledger accounts. The role column marks control and cash accounts.

Primary key: account_id

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | Account number. |
| `account_name` | string | Account name. |
| `account_type` | string | ASSET, LIABILITY, EQUITY, REVENUE or EXPENSE. |
| `normal_balance` | string | DEBIT or CREDIT. |
| `role` | string | CASH, AP_CONTROL, AR_CONTROL or empty. |

## journal_lines

One row per journal line. Lines with the same je_id form one entry.

Primary key: line_id
Foreign key: account_id to chart_of_accounts.account_id

| Column | Type | Description |
| --- | --- | --- |
| `line_id` | string | Line id. |
| `je_id` | string | Journal entry id. |
| `line_no` | integer | Line number within the entry. |
| `posting_date` | date | Date the entry was posted. |
| `period` | string | Accounting period, YYYY-MM. |
| `account_id` | string | Account posted to. |
| `debit_cents` | integer | Debit amount in cents. |
| `credit_cents` | integer | Credit amount in cents. |
| `memo` | string | Short description. |
| `source_type` | string | OPENING, AP_INVOICE, AP_PAYMENT, AR_INVOICE, AR_RECEIPT or MANUAL. |
| `source_id` | string | Id of the subledger row that posted here, empty for manual entries. |
| `created_by` | string | Role id of the poster. |
| `approved_by` | string | Role id of the approver, empty if none. |

## vendors

Vendor master.

Primary key: vendor_id

| Column | Type | Description |
| --- | --- | --- |
| `vendor_id` | string | Vendor id. |
| `vendor_name` | string | Vendor name. |
| `category` | string | Spend category. |
| `terms_days` | integer | Payment terms in days. |

## ap_invoices

Vendor invoices. Each posts to one journal entry.

Primary key: invoice_id
Foreign key: vendor_id to vendors.vendor_id
Foreign key: expense_account_id to chart_of_accounts.account_id
Foreign key: je_id to journal_lines.je_id

| Column | Type | Description |
| --- | --- | --- |
| `invoice_id` | string | Invoice id. |
| `vendor_id` | string | Vendor. |
| `invoice_number` | string | Number printed on the vendor invoice. |
| `invoice_date` | date | Invoice and posting date. |
| `due_date` | date | Due date. |
| `amount_cents` | integer | Invoice total in cents. |
| `expense_account_id` | string | Debit account. |
| `je_id` | string | Journal entry it posted to. |
| `created_by` | string | Role id that entered it. |
| `approved_by` | string | Role id that approved it. |

## ap_payments

Payments to vendors. Each posts to one journal entry.

Primary key: payment_id
Foreign key: vendor_id to vendors.vendor_id
Foreign key: invoice_id to ap_invoices.invoice_id
Foreign key: je_id to journal_lines.je_id

| Column | Type | Description |
| --- | --- | --- |
| `payment_id` | string | Payment id. |
| `vendor_id` | string | Vendor paid. |
| `invoice_id` | string | Invoice paid. |
| `payment_date` | date | Payment and posting date. |
| `amount_cents` | integer | Amount paid in cents. |
| `method` | string | ACH or CHECK. |
| `je_id` | string | Journal entry it posted to. |
| `created_by` | string | Role id that entered it. |
| `approved_by` | string | Role id that approved it. |

## customers

Customer master.

Primary key: customer_id

| Column | Type | Description |
| --- | --- | --- |
| `customer_id` | string | Customer id. |
| `customer_name` | string | Customer name. |
| `terms_days` | integer | Payment terms in days. |

## ar_invoices

Customer invoices. Each posts to one journal entry.

Primary key: invoice_id
Foreign key: customer_id to customers.customer_id
Foreign key: je_id to journal_lines.je_id

| Column | Type | Description |
| --- | --- | --- |
| `invoice_id` | string | Invoice id. |
| `customer_id` | string | Customer billed. |
| `invoice_number` | string | Invoice number. |
| `invoice_date` | date | Invoice and posting date. |
| `due_date` | date | Due date. |
| `amount_cents` | integer | Invoice total in cents. |
| `je_id` | string | Journal entry it posted to. |
| `created_by` | string | Role id that entered it. |

## ar_receipts

Customer receipts. Each posts to one journal entry.

Primary key: receipt_id
Foreign key: customer_id to customers.customer_id
Foreign key: invoice_id to ar_invoices.invoice_id
Foreign key: je_id to journal_lines.je_id

| Column | Type | Description |
| --- | --- | --- |
| `receipt_id` | string | Receipt id. |
| `customer_id` | string | Customer paying. |
| `invoice_id` | string | Invoice paid. |
| `receipt_date` | date | Receipt and posting date. |
| `amount_cents` | integer | Amount received in cents. |
| `je_id` | string | Journal entry it posted to. |
| `created_by` | string | Role id that entered it. |

## bank_transactions

Bank statement lines. Each clears one payment or receipt, a few business days after its GL date.

Primary key: bank_txn_id

| Column | Type | Description |
| --- | --- | --- |
| `bank_txn_id` | string | Bank line id. |
| `bank_date` | date | Date the item cleared the bank. |
| `amount_cents` | integer | Signed amount in cents, negative for money out. |
| `ref_type` | string | AP_PAYMENT, AR_RECEIPT or OPENING. |
| `ref_id` | string | Id of the payment or receipt it clears. For OPENING, the journal entry id. |

## reconciling_items

Items in the GL cash balance but not yet on the bank statement at a month end.

Primary key: month_end, ref_id

| Column | Type | Description |
| --- | --- | --- |
| `month_end` | date | Month end the item belongs to. |
| `item_type` | string | OUTSTANDING_PAYMENT or DEPOSIT_IN_TRANSIT. |
| `ref_type` | string | AP_PAYMENT or AR_RECEIPT. |
| `ref_id` | string | Payment or receipt id. |
| `gl_date` | date | Date posted to the GL. |
| `bank_date` | date | Date it cleared the bank. |
| `amount_cents` | integer | Signed effect on GL cash in cents. |

## labels

One row per injected anomaly. Journal anomalies point to the first line of the entry; every line with the same je_id is part of it. A split_invoice label points to the first invoice of the group and lists the others in details.

Primary key: table, row_id, anomaly_type

| Column | Type | Description |
| --- | --- | --- |
| `table` | string | Table holding the row. |
| `row_id` | string | Primary key of the labeled row. |
| `anomaly_type` | string | Kind of anomaly. |
| `details` | string | Short plain description. |
