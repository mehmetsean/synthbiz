from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.check import run_checks
from synthbiz.generate import Params, generate


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    months=st.integers(min_value=1, max_value=4),
    rate=st.floats(min_value=0.0, max_value=0.5),
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)),
)
def test_all_rules_pass_for_any_seed(
    seed: int, months: int, rate: float, start: date
) -> None:
    ds = generate(Params(seed=seed, months=months, anomaly_rate=rate, start_date=start))
    for r in run_checks(ds.tables):
        assert r.ok, (r.rule, r.messages[:3])
    assert len(ds.labels) == ds.anomaly_count


@settings(max_examples=10, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=1000),
    size=st.sampled_from(["medium", "large"]),
)
def test_bigger_sizes_pass(seed: int, size: str) -> None:
    ds = generate(Params(seed=seed, months=1, size=size, anomaly_rate=0.05))
    assert all(r.ok for r in run_checks(ds.tables))
