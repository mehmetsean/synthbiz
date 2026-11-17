# Examples

## seed42-3m

A small committed sample. It is synthetic data. License: CC BY 4.0.

Made with this exact command:

    synthbiz generate --seed 42 --months 3 --size small --anomaly-rate 0.04 --out examples/seed42-3m

The rate is 0.04 because it is the first rate in 0.01 steps (starting at 0.02)
that plants at least three anomaly types.

Inside:

- ten table files, one CSV per table
- labels.csv, one row per planted anomaly
- schema.json and data_dictionary.md
- README.txt with the synthetic notice
- manifest.json with the seed, parameters and a sha256 of every file

Check it:

    synthbiz check examples/seed42-3m

A test in tests/test_examples.py regenerates the folder and compares every file
byte for byte.

Synthetic data for testing and learning only. Any match with a real business is
unintended. Decision support only, not legal, tax, accounting or assurance
advice. No guarantee of compliance.
