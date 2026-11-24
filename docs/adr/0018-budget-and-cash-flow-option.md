# 18. Budget lines and cash flow entries are an option

Status: Accepted

## Context

A finance reporting tool needs a budget to compare with actuals, and a cash flow with investing and financing lines. The ledger had no budget, no fixed assets, no debt and one equity entry. Existing seeds, examples, README numbers and the demo must stay as they are.

## Decision

`Params(budget_and_cash_flow=True)`, or `synthbiz generate --budget-and-cash-flow`, adds two things. The default is off, and an off run is unchanged. The code is in `src/synthbiz/plan.py`.

Cash flow entries:

- Five chart rows with roles: FIXED_ASSET, ACCUM_DEPRECIATION, LOAN, EQUITY_CONTRIBUTION and DEPRECIATION.
- Journal entries for equipment purchases, monthly straight line depreciation, one loan draw, monthly loan repayments and one owner contribution. The schedule is fixed code with no random draws, so it does not move the random stream. The README numbers block prints the totals for the example run.
- Each entry that moves cash has one bank line with ref_type GL_ENTRY and the entry id as ref_id. The bank date equals the posting date, so `bank_ties_to_gl_cash` needs no reconciling item for them. Depreciation moves no cash and has no bank line.
- If a month has no business day, its entries move to the nearest business day inside the date range.

Budget lines:

- A table `budget_lines` (budget_id, period, account_id, amount_cents) with one row per period and revenue or expense account, zero where there was no activity.
- Every amount is first set to the journal result for that cell. Then a set of cells is changed on purpose: a share of the cells whose result is at least a fixed minimum, and at least one cell when any qualifies. The changes alternate between a percent of the result and a fixed amount. The share, the minimum, the percent steps and the fixed amounts are constants at the top of plan.py, and the README numbers block prints the first two.
- The changes use their own random stream, seeded from the run seed, so they do not move the main stream.
- Each changed cell has a row in labels.csv with table budget_lines, the budget id, the type budget_variance_pct or budget_variance_amount, and details that end in `delta_cents=<signed cents>`. A reader derives the planted set from labels.csv and the journal, with no seed ids written into code.
- `anomaly_count` in the manifest counts only the journal and subledger anomalies. The manifest has `budget_variance_count` when the option is on.

The table is optional in the schema: `TABLE_NAMES` keeps the ten original tables, `OPTIONAL_TABLE_NAMES` lists budget_lines, and `schema_dict(with_optional=True)` adds it. `read_dataset` reads the file when it exists. `check` adds the rule `budget_ties_to_journal` only when the table is present.

Options considered:

- Make the new tables and accounts default. This changes every existing file, hash, example and the demo.
- A separate command like `workforce` (ADR 17). A budget needs the journal result of the same run, so a separate generator would have to read the finance output back in.
- An option on `generate` (chosen). One run gives a ledger, a budget and a cash flow that tie.

## Consequences

Budgets equal actuals except at the labeled cells. They do not model a real budgeting process. The loan has no interest and the assets have no disposals. Amounts are made up and not real-world statistics.

Existing consumers that read `TABLE_NAMES` see no change. `scripts/reproduce_readme.py --check` prints the example numbers, and the tests in `tests/test_plan_*.py` check the identities with values derived by hand.
