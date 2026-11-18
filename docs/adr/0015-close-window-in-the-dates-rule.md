# 15. The close window in the dates rule

Status: Accepted. Extends ADR 5.

## Context

The ledger needs accruals for the previous month, booked early in the next month. In the ledger that is a line whose period is the previous month and whose posting date is early in the month. ADR 5 flagged every such line unless it was a labeled out_of_period_entry, so the generator could not make this normal case.

## Decision

A line passes the dates rule when its period is the previous month of its posting date and the posting date is on or before the 3rd business day of its month. The number is the constant CLOSE_WINDOW_BUSINESS_DAYS in dates.py, with the helpers in the same file. Every other mismatch is still a finding unless the line is labeled out_of_period_entry. The generator never plants an out_of_period_entry inside the close window, so a labeled entry is never confused with a normal close accrual. A day after the window always exists: a run ends on a month end, and every month has far more than 3 business days, so the last business day of the run is after the 3rd business day of its month. The fallback to any business day in the code is never reached.

## Consequences

A period two months back, or a previous-period line on the 4th business day, still fails. A tool that flags every period mismatch now raises false alarms on the close accruals. The rule stays one small function and needs no outside data.
