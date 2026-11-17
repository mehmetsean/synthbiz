# Third-party notices

The synthbiz code, docs and sample data are all rights reserved, see LICENSE.
The parts below belong to other people and keep their own licenses.
None of them are copied into this repo.

## Loaded by the demo page

The demo page in site/ loads these from cdn.jsdelivr.net at runtime. They are not bundled.

| Part | Version | License |
| --- | --- | --- |
| Pyodide | 314.0.8 | MPL-2.0 |
| micropip | as bundled with Pyodide 314.0.8 | MPL-2.0 |

## Optional extra

| Part | License |
| --- | --- |
| pyarrow (the parquet extra) | Apache-2.0 |

## Build tool

| Part | License |
| --- | --- |
| hatchling | MIT |

## Dev tools

These are installed with the dev extra, together with pyarrow. They are used to test and check the code only.

| Part | License |
| --- | --- |
| pytest | MIT |
| pytest-cov | MIT |
| hypothesis | MPL-2.0 |
| ruff | MIT |
| mypy | MIT |
| pyyaml | MIT |

To check a Python package license, install it and run `pip show <name>`. To check Pyodide and micropip, open the LICENSE file at https://github.com/pyodide/pyodide and https://github.com/pyodide/micropip.
