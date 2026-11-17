# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

Changes for v0.1.0, not yet released:

### Added

- `synthbiz generate` writes ten linked finance tables for one fictional small manufacturer, with a seed, months, size and anomaly rate.
- Labeled anomalies in labels.csv: duplicate and near-duplicate payments, split invoices, round amounts, weekend and holiday postings, unusual user, missing approval and out-of-period entries.
- `synthbiz check` runs balanced_entries, ap_ar_subledger_ties, bank_ties_to_gl_cash, links, dates and manifest checks.
- CSV output, with Parquet as an optional extra.
- schema.json, data_dictionary.md, README.txt and manifest.json in every output folder.
- Same seed and version give byte-identical files.
- A browser demo in `site/` that runs with Pyodide, and `synthbiz.demo` as its Python entry point.
- A committed sample in `examples/seed42-3m`.
- `scripts/reproduce_readme.py` to rebuild the README numbers.
- Architecture decision records in `docs/adr/`.
