# 13. Row cap and integer form

Status: Accepted

## Context

`_read_parquet` read the whole file and built every row as a Python dict before any check limit applied. A small, highly compressed Parquet file can declare millions of rows, so `synthbiz check` could use a large amount of memory on a crafted folder. A CSV file has the same problem on a smaller scale. Integer columns also accepted anything that Python `int()` parses, such as " 5", "1_000", "+5", non-ASCII digits and numbers with thousands of digits.

## Decision

`MAX_ROWS_PER_FILE = 3_000_000` in `src/synthbiz/io.py`. For Parquet, the row count is read from the file metadata with `pq.ParquetFile`, and a file over the cap is refused with a one-line ValueError naming the file before any data is read. For CSV, rows are counted while reading and the reader stops as soon as the count passes the cap.

Integer columns accept only `-?[0-9]{1,18}` (ASCII digits, matched with `re.fullmatch`). The error text is the existing "is not a valid integer" line.

Options considered:

- No cap. Simple, but a small crafted file can declare far more rows than memory holds.
- A cap on file size. It is easy to read, but a compressed Parquet file is small on disk and large in memory, so it does not bound the rows.
- A cap on rows, read from the Parquet metadata (chosen). It bounds the work before any data is read, and it is the same number for CSV and Parquet.

Why 3,000,000: the largest data generate can make (size large, 1200 months, anomaly rate 0.5, seed 42) has a largest table of 1,426,918 rows (journal_lines), and the cap is more than 2 times that. Other tables in that run: bank_transactions 284,686, ap_invoices 223,975, ap_payments 187,655, ar_invoices 108,000, ar_receipts 97,030, vendors 14,594, reconciling_items 29,688, customers 50, chart_of_accounts 11, and 130,800 labels. To check these numbers:

```
python -c "import sys; sys.path.insert(0,'src'); from synthbiz.generate import generate, Params; ds=generate(Params(size='large', months=1200, anomaly_rate=0.5, seed=42)); print({k: len(v) for k, v in ds.tables.items()}, len(ds.labels))"
```

tests/test_read_limits.py, test_cap_is_above_the_measured_largest_table, asserts the constant against the journal_lines number without generating the data. test_parquet_over_cap_is_refused_before_reading fails if the Parquet data is read, and test_csv_over_cap_stops covers CSV.

18 digits fit in a 64-bit integer, and amounts are in cents, so the limit is far above any generated value.

## Consequences

Files with more than 3,000,000 rows are refused. A Parquet file is now opened with `ParquetFile` and read once, after the count is known to be within the cap. Integer values of 19 digits or more, and forms with spaces, underscores or a plus sign, are rejected in both CSV and Parquet.
