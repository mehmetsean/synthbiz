# 6. generate refuses a non-empty folder unless --force

Status: Accepted

## Context

Writing into a folder that already holds other files can destroy them or mix two datasets.

## Decision

generate stops when --out is not empty. With --force it removes only files with known synthbiz names and leaves everything else. The manifest lists only the files written in that run.

## Consequences

A mistake cannot delete unrelated files. A stale file of a known name is removed, so the folder always holds one dataset.
