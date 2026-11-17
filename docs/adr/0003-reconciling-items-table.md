# 3. A tenth table, reconciling_items, and the links rule

Status: Accepted

## Context

Bank balance and GL cash differ at a month end because payments and receipts clear a few days after posting. A check needs the list of those items, and a reader needs to see it.

## Decision

Add a table reconciling_items with one row per outstanding payment or deposit in transit at each month end. The bank tie check compares bank balance plus these items with GL cash and also checks the table itself. The links rule checks that every key in the schema, and every label, points to a real row.

## Consequences

The bank tie is visible and testable. The table is derived data, so it must be rebuilt whenever bank dates change.
