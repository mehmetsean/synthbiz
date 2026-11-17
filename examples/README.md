# Examples

## seed42-3m

A small committed sample. It is synthetic data.

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan

Made with this exact command:

    synthbiz generate --seed 42 --months 3 --size small --anomaly-rate 0.04 --out examples/seed42-3m

The rate is 0.04 because it is the first rate in 0.01 steps (starting at 0.02)
that plants at least three anomaly types.
To check, run the command above with --anomaly-rate 0.02.
Then run it again with 0.03, using a new --out folder each time.
Count the distinct anomaly_type values in each labels.csv.
You get 1 type at 0.02 and 2 types at 0.03.

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

Synthetic data for testing and learning only. Any match with a real business is unintended. Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance.
