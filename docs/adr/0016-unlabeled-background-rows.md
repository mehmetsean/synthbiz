# 16. Unlabeled background rows

Status: Accepted

## Context

The clean ledger had no weekend, holiday, unapproved, round-amount, recurring or rare-poster activity. Any rule built on those signals scored a precision of 1.0 on synthbiz data, which says nothing about the rule.

## Decision

By default, a last generation step adds legitimate activity of eight kinds that look like anomalies on the surface. These rows are not in labels.csv. Dataset.background lists them, and manifest.json holds `background_counts` per kind and `approval_limit_cents`. The step runs after the base activity and the planted anomalies and uses the same random stream, so every other row, id and value is the same with background on or off. `--no-background` turns it off. A new labeled type, typo_duplicate_payment, covers a duplicate whose invoice number has one typo. The weekly freight invoices have numbers that differ by one digit on purpose, as a hard negative for that type. Planted rows keep a normal memo, as in ADR 4, and human_weekend_close cannot be told from a planted weekend_posting by its columns.

## Consequences

Rules that flag these rows show a real false alarm rate on synthetic data. A reader cannot find the background rows in the files, only count them in the manifest. Output files and the golden checksums change for the default settings. With background off, the journal and bank files for seed 42 keep their old bytes when the rotation does not reach a changed anomaly type.
