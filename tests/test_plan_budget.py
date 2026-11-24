import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthbiz.plan import (
    BUDGET_MIN_ACTUAL_CENTS,
    BUDGET_VARIANCE_RATE,
    actual_by_cell,
    plan_budget,
)

COA = [
    {"account_id": "1000", "account_type": "ASSET"},
    {"account_id": "4000", "account_type": "REVENUE"},
    {"account_id": "6100", "account_type": "EXPENSE"},
    {"account_id": "6200", "account_type": "EXPENSE"},
]


def line(period: str, account: str, debit: int, credit: int) -> dict[str, object]:
    return {
        "period": period,
        "account_id": account,
        "debit_cents": debit,
        "credit_cents": credit,
    }


LINES = [
    line("2025-01", "1000", 900_000, 0),
    line("2025-01", "4000", 0, 900_000),
    line("2025-01", "6100", 250_000, 0),
    line("2025-01", "6100", 0, 50_000),
    line("2025-02", "6100", 120_000, 0),
    line("2025-02", "4000", 0, 40_000),
]


def test_actuals_by_hand() -> None:
    got = actual_by_cell(COA, LINES)
    assert got == {
        ("2025-01", "4000"): 900_000,
        ("2025-01", "6100"): 200_000,
        ("2025-01", "6200"): 0,
        ("2025-02", "4000"): 40_000,
        ("2025-02", "6100"): 120_000,
        ("2025-02", "6200"): 0,
    }


def test_actuals_without_lines() -> None:
    assert actual_by_cell(COA, []) == {}


def test_no_eligible_cell_means_budget_equals_actual() -> None:
    small = [line("2025-01", "6100", BUDGET_MIN_ACTUAL_CENTS - 1, 0)]
    rows, labels = plan_budget(COA, small, 1)
    assert labels == []
    assert [r["amount_cents"] for r in rows] == [0, BUDGET_MIN_ACTUAL_CENTS - 1, 0]


def test_rows_are_sorted_with_ids() -> None:
    rows, _ = plan_budget(COA, LINES, 1)
    assert [r["budget_id"] for r in rows] == [f"BL-{n:06d}" for n in range(1, 7)]
    keys = [(r["period"], r["account_id"]) for r in rows]
    assert keys == sorted(keys)
    assert len(rows) == 6


def delta_of(label: dict[str, str]) -> int:
    m = re.search(r"delta_cents=(-?[0-9]+)$", label["details"])
    assert m is not None
    return int(m.group(1))


def test_labels_name_the_changed_cells() -> None:
    rows, labels = plan_budget(COA, LINES, 7)
    actual = actual_by_cell(COA, LINES)
    by_id = {r["budget_id"]: r for r in rows}
    assert len(labels) == 1
    lab = labels[0]
    assert lab["table"] == "budget_lines"
    row = by_id[lab["row_id"]]
    cell = (row["period"], row["account_id"])
    assert actual[cell] >= BUDGET_MIN_ACTUAL_CENTS
    assert row["amount_cents"] == actual[cell] + delta_of(lab)
    assert delta_of(lab) != 0
    for r in rows:
        if r["budget_id"] != lab["row_id"]:
            assert r["amount_cents"] == actual[(r["period"], r["account_id"])]


def test_one_eligible_cell_is_still_planted() -> None:
    one = [line("2025-01", "6100", BUDGET_MIN_ACTUAL_CENTS, 0)]
    rows, labels = plan_budget(COA, one, 1)
    assert len(labels) == 1
    assert labels[0]["row_id"] == "BL-000002"
    assert len(rows) == 3


def test_same_seed_same_result() -> None:
    assert plan_budget(COA, LINES, 3) == plan_budget(COA, LINES, 3)


def test_variance_count_follows_rate() -> None:
    lines = [
        line(f"2025-{m:02d}", a, 500_000, 0)
        for m in range(1, 11)
        for a in ("6100", "6200")
    ]
    _, labels = plan_budget(COA, lines, 1)
    eligible = 20
    assert len(labels) == round(BUDGET_VARIANCE_RATE * eligible)
    assert {lab["anomaly_type"] for lab in labels} == {
        "budget_variance_pct",
        "budget_variance_amount",
    }


@settings(max_examples=60, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=100_000),
    amounts=st.lists(
        st.integers(min_value=0, max_value=5_000_000), min_size=1, max_size=40
    ),
)
def test_labels_match_planted_cells(seed: int, amounts: list[int]) -> None:
    lines = [
        line(f"2025-{(i % 12) + 1:02d}", "6100" if i % 2 else "6200", amt, 0)
        for i, amt in enumerate(amounts)
    ]
    rows, labels = plan_budget(COA, lines, seed)
    actual = actual_by_cell(COA, lines)
    labeled = {lab["row_id"]: delta_of(lab) for lab in labels}
    assert len(labeled) == len(labels)
    for r in rows:
        want = actual[(r["period"], r["account_id"])] + labeled.get(r["budget_id"], 0)
        assert r["amount_cents"] == want
        assert r["amount_cents"] >= 0
    pct = [lab for lab in labels if lab["anomaly_type"] == "budget_variance_pct"]
    for lab in pct:
        row = next(r for r in rows if r["budget_id"] == lab["row_id"])
        base = actual[(row["period"], row["account_id"])]
        d = abs(delta_of(lab)) * 10_000
        assert 1000 * base - 10_000 <= d <= 3000 * base


def test_rejects_unknown_account() -> None:
    with pytest.raises(ValueError, match=re.escape("journal line account 9999")):
        actual_by_cell(COA, [line("2025-01", "9999", 1, 0)])
