# synthbiz spec (v0.1 to v0.4)

## Problem
People who build finance and operations analytics need test data that behaves like one company's books: linked tables that reconcile, with known problems planted in them. Real ledgers cannot be shared. Row-by-row fake-data tools such as Faker generate each row on its own, so nothing ties an invoice to a ledger posting or a payment to a bank statement. Fixed sample datasets cannot be resized or reseeded. Without labels, nobody can measure whether a duplicate-payment check or a bank match actually works.

## User
- Data and analytics engineers who test finance pipelines, reconciliations and dashboards.
- Instructors and students in accounting analytics and data analytics courses.
- People building anomaly detection or matching tools who need labeled ground truth.
- The later repos in this program (ledgercheck, capplan, triage-lab, cashplan13), which read synthbiz output.

## MVP scope
Python 3.11+ library and CLI: `synthbiz generate --seed 42 --months 12 --out data/` and `synthbiz check data/`.
One fictional company: a small manufacturer with a size setting (vendors, customers, invoice volume).

v0.1, finance core (what ledgercheck needs first):
- Tables: chart_of_accounts, journal_lines, vendors, ap_invoices, ap_payments, customers, ar_invoices, ar_receipts, bank_transactions, reconciling_items.
- `check` verifies: every journal entry balances; AP and AR subledgers tie to their control accounts at each month end; bank balance ties to GL cash after listed reconciling items; every key and label points to a real row; dates and periods are consistent; files match manifest.json.
- Anomalies injected at a set rate, each written to labels.csv (table, row id, type, details): exact, near-duplicate (vendor name variants) and typo-duplicate (invoice number with one typo) payments, invoices split under an approval limit, round-amount entries, weekend and holiday postings, postings by an unusual user, missing approval, out-of-period entries.
- CSV output, Parquet as an optional extra. schema.json plus a generated data dictionary.
- Same seed and version give byte-identical files, with a checksum manifest.

v0.2, realism: legitimate unlabeled background rows, typo duplicate payments, and the approval limit in manifest.json (so rules can be scored on false alarms).
v0.3, assets and maintenance: assets, depreciation and maintenance work orders, tied to the GL and to AP for parts (for capplan).
v0.4, tickets and inventory: help-desk tickets linked to vendors, customers and assets (for triage-lab); inventory and purchase orders.
Workforce tables (unreleased): staff, shifts, demand and availability for shift scheduling tools, as a separate `synthbiz workforce` command. See ADR 17.

## Non-goals
- No training on, or imitation of, any real company's data.
- No payroll, tax calculation or multi-currency.
- No privacy-preserving synthesis of a user's own data. That is a different product.
- No server or web app. The demo is a static page.

## Demo plan
- A static GitHub Pages page runs the generator in the browser with Pyodide: choose seed, months and anomaly rate, preview tables, download a zip, see the `check` results. The pyodide.js script tag is pinned to one version with a subresource integrity hash. The files Pyodide loads after that are not covered by it, see docs/adr/0009. Nothing leaves the browser. Check: after the page loads, the browser Network tab shows no requests carrying seed, table or output data.
- A small committed sample (seed 42, 3 months) under examples/ with its checksum.

## Test plan
- Unit tests for each generator.
- Property tests with hypothesis across random seeds for every `check` rule.
- Golden test: the seed 42 checksum is stable within a minor version.
- Label tests: injected count equals label count, and every label points to a real row.
- scripts/reproduce_readme.py regenerates every number quoted in the README.
- CI: ruff, mypy, pytest, and at least 90 percent line coverage on the core package.

## License
All rights reserved, see LICENSE. The chart of accounts and the name word lists are written for this repo. Any outside list (for example a holiday calendar) is recorded in DATA.md with its license.

## Liability notes
- README.txt and data_dictionary.md in every output folder say "synthetic data", and schema.json and manifest.json set "synthetic": true. CSV files keep a plain header row. `synthbiz check` reads them with Python's csv module. Company names are built from neutral word parts, and a note says any match with a real business is unintended.
- No person names: users and approvers are role IDs such as AP_CLERK_1.
- No real bank names, routing numbers, account numbers that pass checksum rules, or tax ID patterns.
- No claim that the data matches real-world statistics.
- Synthetic data for testing and learning only. Any match with a real business is unintended. Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance.
