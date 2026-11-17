# 4. Planted journal anomalies keep a normal memo

Status: Accepted

## Context

Labels tell which rows are anomalies. If the memo text of a planted row also gave it away, a detection tool could score well by reading the memo.

## Decision

A planted journal entry keeps an ordinary memo, like any other entry. The answer is only in labels.csv, which lists the table, row id, type and details.

## Consequences

Tests of detection tools are fair. A person reading the ledger cannot find anomalies from memo text.
