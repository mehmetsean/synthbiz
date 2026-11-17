# Contributing

## Dev setup

    git clone https://github.com/mehmetsean/synthbiz
    cd synthbiz
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"

## Checks to run before a pull request

These are the same commands CI runs.

    ruff check .
    ruff format --check .
    mypy --strict src
    pytest
    python scripts/reproduce_readme.py --check

If you change generated output, update the README numbers with `python scripts/reproduce_readme.py` and regenerate `examples/seed42-3m` with the command in `examples/README.md`.

## Rules

- One feature per pull request.
- Write tests first for core logic.
- Synthetic data only. Never add real company data, real names or real account numbers.
- Plain, short English. No em-dash or en-dash characters.
- Sign off every commit with `git commit -s`. This adds a Signed-off-by line that says you accept the Developer Certificate of Origin: https://developercertificate.org/

Synthetic data for testing and learning only. Any match with a real business is unintended. Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance.
