# 12. Input limits in check

Status: Accepted

## Context

A received folder can hold any dates the reader accepts. Python 3.11 and later parse forms such as 20240131 and 2024-W05-3. As strings, 20240131 sorts after 2024-02-01, so check would compare them wrongly. To see it: python3 -c "print('20240131' < '2024-02-01')" prints False. Two journal lines dated 0001-01-31 and 9999-12-31 give about 120,000 month ends. Each matched bank row with an early GL date and a late bank date creates one reconciling item for each month end in between. 3,000 such rows over 1,200 month ends make 3,600,000 items, far above the limit.

## Decision

Date columns are read only in the form YYYY-MM-DD, with a valid calendar date. Any other form gets the usual one-line error with the file, the row or line and the column.

check stops with a ValueError when the journal lines span more than 1200 months (100 years). The test runs once, in `month_ends_from_lines`, before any per-month work. generate refuses more than 1200 months. `reconciling_items` stops with a ValueError as soon as the item count would pass 200,000. It counts the window of each bank row before building any item, so memory stays bounded. The CLI prints these errors as one line and exits with 1.

Options considered:

- No limit. Simple, but a folder with a long date span or many matched bank rows can make check build very large lists.
- Limit the span only. It stops the 120,000 month case, but 1200 months with 3,000 long-open bank rows would list 3,600,000 items, above the limit.
- Limit the span and the item count (chosen). Both inputs of the growth are bounded.

Why these numbers: 1200 months is 100 years. The largest run in benchmarks/bench.py uses 36 months. For the item limit, generate with size large, 1200 months, anomaly rate 0.5 and seed 42 makes 29,688 reconciling items, so 200,000 leaves about 6.7 times headroom. To check that number:

```
python -c "import sys; sys.path.insert(0,'src'); from synthbiz.generate import generate, Params; print(len(generate(Params(size='large', months=1200, anomaly_rate=0.5)).tables['reconciling_items']))"
```

tests/test_input_limits.py, test_generated_data_stays_far_below_item_limit, checks that size large with 36 months lists under 1 percent of the item limit. The same file has a test of the real limit: exactly 200,000 items pass and one more raises. The limits are constants in `check.py`.

## Consequences

Folders beyond the limits are refused instead of checked. The reference code in benchmarks/baseline.py has no limits and is not edited. Tests that compare it with the new code keep their data inside the limits.
