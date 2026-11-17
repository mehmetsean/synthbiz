# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Fixed

- `synthbiz check` no longer crashes on a bad table file or labels.csv. For wrong or reordered columns, a wrong field count, a blank row, a value that is not an integer or a date, a file that is not UTF-8 or not valid CSV, or an unreadable CSV or Parquet file, it prints one line naming the file and the problem, and exits with 1. A UTF-8 BOM is accepted.
- `synthbiz check` now prints "SKIP labels" when labels.csv is missing, and the last line says how many checks were skipped. To hand out data without the answer file, remove both labels.csv and manifest.json.
- The spec no longer says all Pyodide files have an integrity hash. Only the pyodide.js script tag does, as docs/adr/0009 says.
- The Pages workflow file did not parse, so the demo page never deployed. A test now loads every workflow file.

### Added

- The CodeQL workflow can be started by hand.

## 0.1.0 - 2026-11-17

First release.

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
