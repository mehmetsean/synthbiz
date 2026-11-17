# 2. Plain CSV header row, notice in side files

Status: Accepted

## Context

The data must be clearly synthetic. A notice inside a CSV file would break standard readers, because the first row must be the header.

## Decision

Every CSV file has a plain header row and nothing else above it. The synthetic notice lives in README.txt, data_dictionary.md, schema.json and manifest.json of every output folder. schema.json and manifest.json set synthetic to true.

## Consequences

CSV files have a plain header row and load with Python's csv module, which `synthbiz check` uses. The notice travels with the folder, but not inside each file.
