import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.plan import (
    EQUIPMENT_BUYS,
    LIFE_MONTHS,
    LOAN_DRAW_CENTS,
    cash_schedule,
    depreciation_for,
)


def test_three_month_schedule_by_hand() -> None:
    assert cash_schedule(3) == [
        (0, "EQUIPMENT_PURCHASE", 24_000_000),
        (1, "LOAN_DRAW", 30_000_000),
        (1, "DEPRECIATION", 400_000),
        (2, "DEPRECIATION", 400_000),
        (2, "LOAN_REPAYMENT", 1_000_000),
    ]


def test_one_month_has_only_the_first_purchase() -> None:
    assert cash_schedule(1) == [(0, "EQUIPMENT_PURCHASE", 24_000_000)]


def test_twelve_month_totals_by_hand() -> None:
    events = cash_schedule(12)
    total = {}
    for _, kind, cents in events:
        total[kind] = total.get(kind, 0) + cents
    assert total == {
        "EQUIPMENT_PURCHASE": 33_000_000,
        "LOAN_DRAW": 30_000_000,
        "OWNER_CONTRIBUTION": 5_000_000,
        "DEPRECIATION": 11 * 400_000 + 5 * 150_000,
        "LOAN_REPAYMENT": 10_000_000,
    }


def test_depreciation_edges() -> None:
    assert depreciation_for(100, 0) == 0
    assert depreciation_for(100, 1) == 1
    assert depreciation_for(100, LIFE_MONTHS) == 100 - (LIFE_MONTHS - 1)
    assert depreciation_for(100, LIFE_MONTHS + 1) == 0
    assert sum(depreciation_for(100, a) for a in range(0, 200)) == 100


def test_loan_is_repaid_once_and_never_below_zero() -> None:
    events = cash_schedule(100)
    repaid = [c for _, k, c in events if k == "LOAN_REPAYMENT"]
    assert sum(repaid) == LOAN_DRAW_CENTS
    assert len(repaid) == 30
    assert all(c > 0 for c in repaid)


def test_depreciation_never_passes_cost() -> None:
    events = cash_schedule(200)
    dep = sum(c for _, k, c in events if k == "DEPRECIATION")
    assert dep == sum(cost for _, cost in EQUIPMENT_BUYS)


@settings(max_examples=60, deadline=None)
@given(months=st.integers(min_value=1, max_value=300))
def test_schedule_is_ordered_and_positive(months: int) -> None:
    events = cash_schedule(months)
    assert events == sorted(events, key=lambda e: e[0])
    assert all(0 <= m < months and c > 0 for m, _, c in events)


@pytest.mark.parametrize("cost", [60, 61, 119, 9_000_000])
def test_depreciation_sums_to_cost(cost: int) -> None:
    assert sum(depreciation_for(cost, a) for a in range(1, LIFE_MONTHS + 1)) == cost
