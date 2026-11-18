# 12. Input limits in check

Status: Accepted

## Context

A received folder can hold any dates the reader accepts. Python parses forms such as 20240131 and 2024-W05-3, and these compare wrongly as strings in check. Two journal lines dated 0001-01-31 and 9999-12-31 give about 120,000 month ends. Each matched bank row with an early GL date and a late bank date then creates a reconciling item for every month end in between, so a few thousand rows can exhaust memory.

## Decision

Date columns are read only in the form YYYY-MM-DD, with a valid calendar date. Any other form gets the usual one-line error with the file, the row or line and the column.

check stops with a ValueError when the journal lines span more than 1200 months (100 years). The test runs once, in `month_ends_from_lines`, before any per-month work. generate refuses more than 1200 months. `reconciling_items` stops with a ValueError as soon as the item count would pass 1,000,000. It counts the window of each bank row before building any item, so memory stays bounded. The CLI prints these errors as one line and exits with 1.

Options considered:

- No limit. Simple, but a small crafted folder can exhaust memory.
- Limit the span only. It stops the 120,000 month case, but 1200 months with thousands of long-open bank rows can still list millions of items.
- Limit the span and the item count (chosen). Both inputs of the growth are bounded.

Why these numbers: 1200 months is 100 years, far longer than any real ledger, and the largest generated run uses 36 months. The generated set for size large and 36 months lists under 1 percent of 1,000,000 items, and a test checks it. The limits are constants in `check.py`.

## Consequences

Folders beyond the limits are refused instead of checked. The reference code in benchmarks/baseline.py has no limits and is not edited. Tests that compare it with the new code keep their data inside the limits.
