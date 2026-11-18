# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Changed

- Integer columns accept only an optional minus sign and 1 to 18 ASCII digits. Forms such as " 5", "1_000" and "+5" are reported as not a valid integer.
- generate refuses a run longer than 1200 months.
- check and the readers accept only YYYY-MM-DD dates. Other forms such as 20240131 are reported as not a valid date.
- check no longer rescans every row for each month end. Balances are bucketed by month end in one pass. generate calls the same reconciling_items code, and its output files are unchanged (tests/test_examples.py compares them byte for byte).
- LICENSE now says that commercial use needs a paid license and how to buy one.
- Demo page redesign: design tokens, light and dark themes, a responsive form and a header with the source link.

### Fixed

- A Parquet file that declares more than 3,000,000 rows is refused from its metadata. A CSV file is stopped once it passes 3,000,000 rows. A folder with more than 5,000,000 rows in total is stopped too.
- check stops with a one-line error for a date span above 1200 months or for more than 200,000 reconciling items, instead of building the full list.

### Added

- benchmarks/bench.py and docs/benchmark.md: timings against the old check code and a simple unlinked generator, with a correctness assertion that CI runs.
- Equivalence tests that compare the checks with the old reference code on random and tampered data.
- Demo summary row with total rows, tables, planted anomalies and checks passed.
- Demo bar chart of planted anomalies by type, with the same numbers in a text table.
- Demo check results show [PASS] and [FAIL] marks, so they do not rely on color alone.

## 0.1.1 - 2026-11-17

### Changed

- License changed to all rights reserved.
- CONTRIBUTING.md removed. Outside code contributions are not accepted.
- README.txt in every generated folder now carries the copyright and license notice.

### Fixed

- `synthbiz check` no longer crashes on a bad table file or labels.csv. For wrong or reordered columns, a wrong field count, a blank row, a value that is not an integer or a date, a file that is not UTF-8 or not valid CSV, a Parquet file with bad values, or an unreadable CSV or Parquet file, it prints one line naming the file and the problem, and exits with 1. A UTF-8 BOM is accepted.
- `synthbiz check` now prints "SKIP labels" when labels.csv is missing, and the last line says how many checks were skipped. Without labels.csv the dates check reports planted out-of-period entries as FAIL, because it cannot tell them from real errors. Remove manifest.json too, or the manifest check fails.
- The spec no longer says all Pyodide files have an integrity hash. Only the pyodide.js script tag does, as docs/adr/0009 says.
- The Pages workflow file did not parse, so the demo page never deployed. A test now loads every workflow file.

### Added

- The CodeQL workflow can be started by hand.
- THIRD_PARTY_NOTICES.md lists the third-party parts and their licenses.
- docs/adr/0010 records the license change. Release 0.1.0 keeps the license it was released with.

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
