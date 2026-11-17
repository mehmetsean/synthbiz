# synthbiz
Seeded synthetic business data that reconciles, with labeled anomalies

Synthetic finance data for one fictional small manufacturer. The tables link to
each other and reconcile, and known problems are planted and labeled so you can
test checks and matching tools. All data is synthetic.

## Use

    uv venv --python 3.12 && uv pip install -e ".[dev]"
    source .venv/bin/activate
    synthbiz generate --seed 42 --months 12 --size small --anomaly-rate 0.02 --out data/
    synthbiz check data/

Parquet output needs the extra: `pip install "synthbiz[parquet]"`, then add
`--format parquet`.

## Numbers in this README

Every number below comes from `python scripts/reproduce_readme.py`. Run it with
`--check` to see if this block still matches a fresh run. The manifest hash
includes the package version, so it changes when the version changes.

<!-- numbers:start -->
Example: seed 42, 12 months, size small, anomaly rate 0.02.

Rows per table:

- chart_of_accounts: 11
- journal_lines: 1030
- vendors: 9
- ap_invoices: 149
- ap_payments: 126
- customers: 6
- ar_invoices: 120
- ar_receipts: 92
- bank_transactions: 219
- reconciling_items: 18
- labels: 6

Total rows: 1780 (not counting labels)

Planted anomalies: 6

- exact_duplicate_payment: 1
- holiday_posting: 1
- near_duplicate_payment: 1
- round_amount_entry: 1
- split_invoice: 1
- weekend_posting: 1

Checks:

- balanced_entries: PASS
- ap_ar_subledger_ties: PASS
- bank_ties_to_gl_cash: PASS
- links: PASS

manifest.json sha256: 1f7810d81b57594c5209c75b0ee1e509d8a68023e00e50f37ee2ebc4a6f200f3
<!-- numbers:end -->

See docs/spec.md for scope and DATA.md for data sources and licenses.

Synthetic data for testing and learning only. Any match with a real business is
unintended. Not accounting, tax or assurance advice.
