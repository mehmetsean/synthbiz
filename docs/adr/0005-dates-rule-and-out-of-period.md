# 5. The dates rule allows a period mismatch only for labeled rows

Status: Accepted

## Context

Each journal line has a posting date and a period. They should agree. An out_of_period_entry anomaly needs them to differ.

## Decision

The dates check fails when a line's period does not match its posting month, unless the line is labeled out_of_period_entry. Due dates, payments and receipts must not be before their invoice.

## Consequences

A period mismatch that is not labeled is a real finding. The check and the labels agree with each other.
