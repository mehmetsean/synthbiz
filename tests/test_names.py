import random
import re

import pytest

from synthbiz.names import (
    company_name,
    customer_names,
    name_variant,
    person_names,
    phase_name,
    task_name,
    vendor_names,
)


def test_vendor_names_unique_and_deterministic() -> None:
    a = vendor_names(random.Random(1), 60)
    b = vendor_names(random.Random(1), 60)
    assert a == b
    assert len(set(a)) == 60


def test_customer_names_unique() -> None:
    names = customer_names(random.Random(2), 50)
    assert len(set(names)) == 50


def test_company_name_has_suffix() -> None:
    assert company_name(random.Random(3)).split()[-1] in {"Co", "Inc", "LLC", "Ltd"}


def test_name_variant_differs_and_keeps_core() -> None:
    rng = random.Random(4)
    for name in vendor_names(rng, 40):
        v = name_variant(name, rng)
        assert v != name
        assert v.split()[0] == name.split()[0]


def test_person_names_unique_deterministic_and_capped() -> None:
    a = person_names(random.Random(4), 500)
    assert a == person_names(random.Random(4), 500)
    assert len(set(a)) == 500
    with pytest.raises(ValueError, match=re.escape("too many names requested")):
        person_names(random.Random(4), 573)


def test_phase_and_task_names() -> None:
    rng = random.Random(3)
    assert re.fullmatch(r"Phase 4: [A-Z][a-z ]+", phase_name(rng, 4))
    for _ in range(200):
        name = task_name(rng)
        assert re.fullmatch(r"[A-Z][a-z]+ [a-z ]+, area ([1-9]|1[0-9]|20)", name)
