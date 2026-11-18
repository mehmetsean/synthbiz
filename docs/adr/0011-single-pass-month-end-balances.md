# 11. Single-pass month-end balances

Status: Accepted

## Context

`check` and `generate` computed every balance at every month end by scanning all rows once per month end. That costs O(M x R) for M month ends and R rows. In the reference column of the docs/benchmark.md table, size large took 0.0391 s at 12 months and 0.5775 s at 36 months, about 15 times longer for 3.1 times the rows. These numbers come from that table. The output files must stay byte for byte the same, and the runtime must stay stdlib only.

## Decision

Bucket each row once with `bisect_left` on the sorted month-end ISO strings. A row dated d belongs to bucket i = bisect_left(ends, d). If i equals the number of month ends, the row is after the last month end and counts nowhere. Bucket sums and a running total give the balance at every month end in O(R log M + M).

`reconciling_items` makes one pass over the bank rows. For a matched row the month ends s with gl_date <= s < bank_date are the slice from bisect_left(ends, gl_date) to bisect_left(ends, bank_date). Items are collected per month end in bank table order, joined in month-end order, then sorted with the same stable key as before, so the list is identical, ties included. `check_links` builds each key set once.

The old code is kept in `benchmarks/baseline.py` as the timing baseline and the test oracle. `tests/test_check_equivalence.py` compares old and new on random and on tampered data.

Options considered:

- Keep the rescan. Simplest code, but the cost grows with M x R and checks slow down as data gets longer.
- Bucketing with bisect (chosen). Small change, no new dependency, same output.
- A full sort of all rows with a merge sweep over the month ends. Also O(R log R + M), but it needs sorted copies of each table and more code for the same gain.
- pandas or numpy. Rejected: they add runtime dependencies and a larger Pyodide download for the browser demo.

## Consequences

Check time grows closer to linearly with rows. Messages, rule names, result order and public function names are unchanged. The private helpers `_gl_balance` and `_open_balance` are replaced by `_gl_balances` and `_open_balances`. The reference code is a frozen copy of the old behavior, so it is not edited. `reconciling_items` sorts its ends, so callers may pass them in any order, and it reads a value only when the old code would have read it. Complexity and timings are in docs/benchmark.md.
