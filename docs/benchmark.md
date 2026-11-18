# Benchmark

This page describes how the check functions are timed and what the numbers mean. The script is `benchmarks/bench.py`. Anyone can rerun it.

## What is measured

For each size (small, medium, large) and each length (3, 12 and 36 months) with seed 42, the script reports the median of N runs, in seconds:

- generate: `synthbiz.generate.generate` for the same parameters.
- unlinked baseline: `benchmarks/baseline.py: unlinked_rows`.
- check (new): `synthbiz.check.run_checks` as it is now.
- check (reference): the old per-month rescan code, kept in `benchmarks/baseline.py`.

Before each timed run the script runs a full garbage collection and turns the collector off while it times, the same way Python's timeit module does, so a collection caused by an earlier case does not land inside a timing.

It also prints the total row count and how many of the 5 rules pass on the synthbiz data and on the baseline data.

## The two baselines

1. Reference checks. These are the check functions from before the single-pass change, copied verbatim. They rescan every row once per month end. They are the timing baseline for check, and they are the oracle in `tests/test_check_equivalence.py`. The script asserts, for every case, that the new results equal the reference results (same rule, same ok flag, same messages). If they differ, it exits with 1. This assertion is what CI runs.
2. Unlinked rows. This is the kind of generator a one-off script would use. For each table it writes the same row count as `generate` and fills the columns with independent random values from `random.Random(seed)`: ids, ISO dates in the range, amounts. No keys are shared between tables and nothing is posted to a ledger. It is a simple speed baseline for generating random rows, and it shows what is lost: on this data 0 of the 5 rules pass, because journal entries do not balance, subledgers do not tie to the ledger, and foreign keys point nowhere. On synthbiz data all 5 pass.

## How to run

From the repo root, with the dev environment installed:

```
python benchmarks/bench.py
```

Options:

```
python benchmarks/bench.py --repeat 7
python benchmarks/bench.py --json results.json
python benchmarks/bench.py --quick --repeat 1
```

`--quick` runs only size small with 3 and 12 months. CI runs the quick form, so CI checks correctness, not speed. There are no timing assertions, because machines differ.

To check that the new code matches the reference on random, tampered and junk data:

```
pytest tests/test_check_equivalence.py
```

## Complexity

M is the number of month ends, R is the total number of rows in the tables a function reads, and L is the number of foreign key columns plus labels. Bucketing uses `bisect` on the sorted month-end strings, so each row costs O(log M).

| function | before | after |
|---|---|---|
| `month_ends_from_lines` | O(R log R) sort of all dates | O(R) min and max (the sort was small next to the rescans, so the gain is small) |
| GL balance per role | O(M x R) | O(R log M + M) |
| AP and AR open balance | O(M x R) | O(R log M + M) |
| bank balance per month end | O(M x R) | O(R log M + M) |
| `reconciling_items` | O(M x R), plus the output sort | O(R log M + K), plus the output sort, K = items listed |
| adjust sum per month end | O(M x K) | O(K + M) |
| `check_links` key sets | O(L x R), one set built per label or key | O(R) per distinct table and column, built once |

The output sort of `reconciling_items` is O(K log K) in both versions.

## Results

Output of `python benchmarks/bench.py --repeat 7` on one laptop:

```
Python 3.12.13 on arm64
Seed 42, median of 7 runs
```

| size | months | rows | generate s | unlinked s | check s (new) | check s (reference) | synthbiz pass | unlinked pass |
|---|---|---|---|---|---|---|---|---|
| small | 3 | 378 | 0.0006 | 0.0012 | 0.0002 | 0.0002 | 5/5 | 0/5 |
| small | 12 | 1780 | 0.0029 | 0.0060 | 0.0009 | 0.0024 | 5/5 | 0/5 |
| small | 36 | 5454 | 0.0095 | 0.0188 | 0.0030 | 0.0207 | 5/5 | 0/5 |
| medium | 3 | 1213 | 0.0019 | 0.0041 | 0.0006 | 0.0008 | 5/5 | 0/5 |
| medium | 12 | 5568 | 0.0089 | 0.0189 | 0.0029 | 0.0090 | 5/5 | 0/5 |
| medium | 36 | 17161 | 0.0279 | 0.0597 | 0.0106 | 0.0719 | 5/5 | 0/5 |
| large | 3 | 3547 | 0.0053 | 0.0121 | 0.0018 | 0.0027 | 5/5 | 0/5 |
| large | 12 | 16498 | 0.0260 | 0.0566 | 0.0101 | 0.0391 | 5/5 | 0/5 |
| large | 36 | 51136 | 0.0858 | 0.1792 | 0.0544 | 0.5775 | 5/5 | 0/5 |

Timings depend on the machine, the Python version and what else is running. Rerun the command to get your own numbers. At 3 months both check versions finish in a few milliseconds or less, so noise dominates. At large with 36 months the new check took 0.0544 s against 0.5775 s for the reference in this run. Runs on the same machine differ from each other, so rerun it a few times to see the spread.
