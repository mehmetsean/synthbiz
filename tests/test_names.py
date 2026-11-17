import random

from synthbiz.names import company_name, customer_names, name_variant, vendor_names


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
