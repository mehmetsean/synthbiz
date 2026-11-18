# 13. Row cap and integer form

Status: Accepted

## Context

`_read_parquet` read the whole file and built every row as a Python dict before any check limit applied. A small, highly compressed Parquet file can declare millions of rows, so `synthbiz check` could use a large amount of memory on a crafted folder. A CSV file has the same problem on a smaller scale. Integer columns also accepted anything that Python `int()` parses, such as " 5", "1_000", "+5", non-ASCII digits and numbers with thousands of digits.

## Decision

`MAX_ROWS_PER_FILE = 3_000_000` and `MAX_TOTAL_ROWS = 5_000_000` in `src/synthbiz/io.py`. For Parquet, the row count is the larger of the footer `num_rows` and the sum of the row group counts, read with `pq.ParquetFile`. A file over the cap, or one that would push the folder total over its cap, is refused with a one-line ValueError naming the file before any data is read. After reading, the table row count is checked again before any Python dict is built. For CSV, data rows are counted while reading and the reader stops as soon as the count passes either cap. Blank lines are not stored and do not count, so trailing blank lines cost no memory. `read_dataset` keeps one running total over every table file and labels.csv.

Integer columns accept only `-?[0-9]{1,18}` (ASCII digits, matched with `re.fullmatch`). The error text is the existing "is not a valid integer" line.

Options considered:

- No cap. Simple, but a small crafted file can declare far more rows than memory holds.
- A cap on file size. It is easy to read, but a compressed Parquet file is small on disk and large in memory, so it does not bound the rows.
- A cap on rows, read from the Parquet metadata (chosen). It bounds the work before any data is read, and it is the same number for CSV and Parquet.
- Per-file cap only. Simple, but 11 files at 3,000,000 rows each would still be 33,000,000 rows.
- A per-file cap plus a total cap over the folder (chosen). The total cap closes that gap.

Why 3,000,000: generate with size large, 1200 months, anomaly rate 0.5 and seed 42 makes a largest table of 1,426,918 rows (journal_lines), and the cap is more than 2 times that. The other tables in that run are bank_transactions 284,686, ap_invoices 223,975, ap_payments 187,655, ar_invoices 108,000, ar_receipts 97,030, reconciling_items 29,688, vendors 14,594, customers 50 and chart_of_accounts 11, plus 130,800 labels. The tables sum to 2,372,607 rows and with labels the folder has 2,503,407 rows, so the total cap of 5,000,000 is about twice the measured total. To check these numbers:

```
python -c "import sys; sys.path.insert(0,'src'); from synthbiz.generate import generate, Params; ds=generate(Params(size='large', months=1200, anomaly_rate=0.5, seed=42)); print({k: len(v) for k, v in ds.tables.items()}, len(ds.labels))"
```

The caps bound the rows read. They do not bound memory by themselves, because each row becomes a Python dict. Memory use at the caps was not measured.

tests/test_read_limits.py, test_cap_is_above_the_measured_largest_table and test_total_cap_is_above_the_measured_total assert the constants against the measured numbers without generating the data. test_parquet_over_cap_is_refused_before_reading and test_parquet_row_groups_are_summed_before_reading fail if the Parquet data is read. test_csv_over_cap_stops, test_exactly_the_cap_is_read_and_one_more_is_refused, test_csv_trailing_blank_lines_do_not_count, test_csv_many_trailing_blank_lines and test_total_cap_over_all_files cover the CSV and total paths. test_parquet_post_read_guard covers the check after reading.

18 digits fit in a 64-bit integer. In the run from the command above, the largest amount is 100000000 cents, which has 9 digits. To check it:

```
python -c "import sys; sys.path.insert(0,'src'); from synthbiz.generate import generate, Params; ds=generate(Params(size='large', months=1200, anomaly_rate=0.5, seed=42)); print(max(abs(int(r[k])) for rows in ds.tables.values() for r in rows for k in ('amount_cents','debit_cents','credit_cents') if k in r))"
```

## Consequences

Files with more than 3,000,000 rows are refused (Parquet) or stopped (CSV), and so is a folder with more than 5,000,000 rows. A Parquet file is opened with `ParquetFile` and read once, after the count is known to be within the caps. Integer values of 19 digits or more, and forms with spaces, underscores or a plus sign, are rejected in both CSV and Parquet.
