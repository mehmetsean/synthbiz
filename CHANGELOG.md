# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Added

- Background rows: legitimate unlabeled activity of eight kinds (weekend and holiday system batches, recurring system entries, close window accruals, a quarter end weekend close, a round rent accrual, a round retainer invoice, weekly fixed freight invoices and rare posters). On by default, `--no-background` and `Params(background=False)` turn it off. See ADR 16.
- New labeled anomaly type typo_duplicate_payment, after near_duplicate_payment in the rotation. There are ten types now.
- manifest.json has `parameters.background`, `background_counts` and `approval_limit_cents`.
- `Dataset.background` and `Builder.mark_background`.

### Changed

- The dates rule allows a previous-period line posted on or before the 3rd business day of its month (the close window). ADR 15.
- out_of_period_entry is never planted inside the close window.
- Default output changes with background on and with the new type in the rotation: the example in examples/seed42-3m, the README numbers and the golden checksums are regenerated. With `--no-background` the journal and bank files keep their 0.1.2 bytes only while the rotation stays within the first two anomaly types (at most two planted anomalies). Seed 42 with 3 months and the default rate is pinned by golden checksums for the journal and bank files in tests/test_io.py.

- Demo previews show money columns as US dollars, for example $12,345.67, right-aligned. The zip download keeps raw cents.
- The demo sends the list of money columns with each table preview. The list comes from the schema.
- Demo preview tables show a hint when a table is wider than its box. Long text cells wrap. Cells over 60 characters, such as anomaly details, sit behind a keyboard-accessible toggle.
- The demo page has one source link, in the header.

### Added

- scripts/make_badges.py writes coverage.svg and tests.svg from pytest output, using only the standard library. The Pages build runs the tests and publishes both files under badges/. The README shows them. No outside badge service is used.
- Tests for the badge script, including contrast ratios and a property test that random coverage values from 0 to 100 and test counts give a valid SVG.
- The Pages build also runs on pull requests, without deploying.
- A browser test of the Generate button, and a CI job that runs it in Chromium. It is not part of the required ci check.
- synthbiz.schema.money_columns(table) returns the money columns of a table.
- A new optional extra, browser, installs Playwright for that test. Runtime dependencies are still empty.
- A test that the zip download keeps raw cents.

## 0.1.2 - 2026-11-17

### Changed

- Integer columns accept only an optional minus sign and 1 to 18 ASCII digits. Forms such as " 5", "1_000" and "+5" are reported as not a valid integer.
- generate refuses a run longer than 1200 months.
- check and the readers accept only YYYY-MM-DD dates. Other forms such as 20240131 are reported as not a valid date.
- check no longer rescans every row for each month end. Balances are summed by month end in one pass. generate uses the same code, and its output files are unchanged. A test compares them byte for byte.
- LICENSE now says that commercial use needs a paid license and how to buy one.
- Demo page redesign: design tokens, light and dark themes, a responsive form and a header with the source link.

### Fixed

- A Parquet file whose metadata declares more than 3,000,000 rows is refused before it is read. A CSV file is stopped once it passes 3,000,000 rows. A folder with more than 5,000,000 rows in total is stopped too.
- check stops with a one-line error for a date span above 1200 months or for more than 200,000 reconciling items, instead of building the full list.

### Added

- benchmarks/bench.py and docs/benchmark.md: timings of check against the old code, and of generate against a simple random-row generator. The script asserts that the new check gives the same results as the old code, and CI runs that assertion.
- Tests that compare the new check with the old code on random and altered data.
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
