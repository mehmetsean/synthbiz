"""Entry points for the browser demo."""

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .check import Result, run_checks
from .generate import SIZES, Params, generate
from .io import read_dataset, verify_manifest, write_dataset
from .schema import money_columns

MAX_MONTHS = 24
MAX_RATE = 0.2
MAX_MESSAGES = 5
ZIP_TIME = (2025, 1, 1, 0, 0, 0)


def _params(seed: int, months: int, size: str, rate: float) -> Params:
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a whole number, 0 or more")
    if type(months) is not int or not 1 <= months <= MAX_MONTHS:
        raise ValueError(f"months must be a whole number from 1 to {MAX_MONTHS}")
    if size not in SIZES:
        raise ValueError(f"size must be one of {sorted(SIZES)}")
    if type(rate) not in (int, float) or not 0 <= rate <= MAX_RATE:
        raise ValueError(f"anomaly rate must be a number from 0 to {MAX_RATE}")
    return Params(seed=seed, months=months, size=size, anomaly_rate=float(rate))


def run_demo(
    seed: int, months: int, size: str, anomaly_rate: float, preview_rows: int = 5
) -> str:
    """Generate a dataset and return counts, previews, labels and checks as JSON."""
    ds = generate(_params(seed, months, size, anomaly_rate))
    with tempfile.TemporaryDirectory() as tmp:
        write_dataset(ds, Path(tmp))
        tables, labels = read_dataset(Path(tmp))
        results = run_checks(tables, labels)
        manifest = verify_manifest(Path(tmp)) or []
        results.append(Result("manifest", not manifest, manifest))
    out: dict[str, Any] = {
        "tables": {
            name: {
                "rows": len(rows),
                "preview": rows[: max(preview_rows, 0)],
                "money": money_columns(name),
            }
            for name, rows in tables.items()
        },
        "labels": labels,
        "anomaly_count": ds.anomaly_count,
        "checks": [
            {"rule": r.rule, "ok": r.ok, "messages": r.messages[:MAX_MESSAGES]}
            for r in results
        ],
    }
    return json.dumps(out)


def demo_zip(seed: int, months: int, size: str, anomaly_rate: float) -> bytes:
    """Return the CSV dataset as a zip. Same inputs give the same bytes."""
    ds = generate(_params(seed, months, size, anomaly_rate))
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        write_dataset(ds, Path(tmp))
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(Path(tmp).iterdir()):
                info = zipfile.ZipInfo(path.name, ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, path.read_bytes())
    return buf.getvalue()
