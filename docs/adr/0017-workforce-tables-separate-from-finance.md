# 17. Workforce tables are a separate generator

Status: Accepted

## Context

A shift scheduling tool needs synthetic staff, shifts, demand and availability. The repo only had the finance ledger. The tool must not fork the generator, and output must be the same on every run for a given seed, so tests can check it.

## Decision

`synthbiz workforce` writes four CSV files: staff.csv, shifts.csv, demand.csv and availability.csv. The code is in `src/synthbiz/workforce.py` with its own `WorkforceParams` (seed, staff, days, start_date) and `generate_workforce`. It does not touch the finance tables, the anomaly rotation or the random stream of `generate`, so existing output is unchanged.

Rules of the data:

- Integer cents for wages and integer minutes for times and weekly limits. Skills in staff.csv are a list joined by `|`.
- Names come from `person_names` in names.py. The counts are in the README numbers block.
- Three shifts: DAY 06:00 to 14:00, EVE 14:00 to 22:00, NIGHT 22:00 to 06:00. NIGHT has `crosses_midnight` 1. Times are minutes after midnight and end may be smaller than start.
- Demand is a share of each skill's headcount per shift, at least 1. Weekend days use a fixed fraction of the weekday need. The shares and the fraction are in the README numbers block. Front desk has no night shift.
- Availability has at most one row per person and date. About 4 percent unavailable, 8 percent prefer_off and 6 percent prefer_on. The `shift_id` column holds a shift id or `*` for the whole day.
- Limits: 1 to 500 staff and 1 to 366 days. Availability rows are at most 183,000, about 33,000 measured at 500 staff and 366 days, far under the read caps of ADR 13.
- Every run writes README.txt with the synthetic data notice and the license line, data_dictionary.md, and manifest.json with `synthetic: true`, parameters, row counts and a sha256 per file. There are no planted anomalies, so there is no labels.csv.

Options considered:

- Add the tables to `generate`. This would change every existing output file, golden checksum and the demo.
- Fork the generator into the scheduling repo. This repeats names and manifest code and can drift.
- A separate generator in synthbiz (chosen). The columns are plain CSV, so a consumer reads the files and does not import synthbiz.

## Consequences

`synthbiz check` does not read workforce folders. Demand and availability are generated independently, so a schedule may not be feasible. Wages, contracts and rates are made up and not real-world statistics.
