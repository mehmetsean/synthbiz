# synthbiz
Seeded synthetic business data that reconciles, with labeled anomalies

Synthetic finance data for one fictional small manufacturer. The tables link to
each other and reconcile, and known problems are planted and labeled so you can
test checks and matching tools. All data is synthetic.

## Use

    uv venv --python 3.12 && uv pip install -e ".[dev]"
    source .venv/bin/activate
    synthbiz generate --seed 42 --months 12 --size small --anomaly-rate 0.02 --out data/
    synthbiz check data/

Parquet output needs the extra: `pip install "synthbiz[parquet]"`, then add
`--format parquet`.

See docs/spec.md for scope and DATA.md for data sources and licenses.

Synthetic data for testing and learning only. Any match with a real business is
unintended. Not accounting, tax or assurance advice.
