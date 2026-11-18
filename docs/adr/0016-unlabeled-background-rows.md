# 16. Unlabeled background rows

Status: Accepted

## Context

The clean ledger had no weekend, holiday, unapproved, round-amount, recurring or rare-poster activity. A rule built on those signals flags only planted rows, so its precision says nothing about the rule.

## Decision

By default, a last generation step adds legitimate activity of eight kinds that look like anomalies on the surface. These rows are not in labels.csv. Dataset.background lists them, and manifest.json holds `background_counts` per kind and `approval_limit_cents`. The step runs after the base activity and the planted anomalies and uses the same random stream, so every base and anomaly row, with its id and values, is the same with background on or off. Two things differ: bank_txn_id, which is renumbered after sorting, and reconciling_items, which is rebuilt from the bank and GL dates. `--no-background` turns it off. A new labeled type, typo_duplicate_payment, covers a duplicate whose invoice number has one typo. The weekly freight invoices have numbers that are one apart, so a rule that uses edit distance 1 on invoice numbers has to tell them apart. Planted rows keep a normal memo, as in ADR 4, and human_weekend_close cannot be told from a planted weekend_posting by its columns.

## Consequences

Rules that flag these rows show a measurable false alarm rate on synthetic data. A reader cannot find the background rows in the files, only count them in the manifest. Output files and the golden checksums change for the default settings. With `--no-background`, the journal and bank files keep their 0.1.2 bytes only while the rotation stays within exact_duplicate_payment and near_duplicate_payment, the two types before typo_duplicate_payment (at most two planted anomalies). Seed 42 with 3 months and the default rate is the pinned case in tests/test_io.py.
