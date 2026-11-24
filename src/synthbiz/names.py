"""Neutral word parts for company names. Written for this repo."""

import random

VENDOR_PREFIXES = [
    "Northfield", "Lakeshore", "Redwood", "Summit", "Harbor", "Cedar",
    "Granite", "Bluewater", "Ironbridge", "Meadow", "Stonegate", "Pinecrest",
    "Clearview", "Eastgate", "Silverline", "Oakridge",
]  # fmt: skip
VENDOR_PRODUCTS = [
    "Fasteners", "Steel", "Plastics", "Packaging", "Freight", "Electric",
    "Tooling", "Coatings", "Lubricants", "Logistics", "Supply", "Metals",
]  # fmt: skip
CUSTOMER_PREFIXES = [
    "Applied", "Metro", "Prairie", "Valley", "Keystone", "Pioneer", "Atlas",
    "Beacon", "Crescent", "Dunmore", "Elmwood", "Fairview", "Greenway",
    "Highland", "Juniper", "Kingsway", "Lowell", "Mapleton", "Newport",
    "Orchard",
]  # fmt: skip
CUSTOMER_INDUSTRIES = [
    "Machinery", "Equipment", "Fabrication", "Assembly", "Industries",
    "Systems", "Products", "Works",
]  # fmt: skip
COMPANY_PREFIXES = ["Westbrook", "Fernhill", "Ashford", "Brightwater", "Marlow"]
COMPANY_PRODUCTS = ["Metalworks", "Components", "Manufacturing", "Precision"]
SUFFIXES = ["Co", "Inc", "LLC", "Ltd", "Corp"]
LONG_SUFFIX = {
    "Co": "Company",
    "Inc": "Incorporated",
    "LLC": "L.L.C.",
    "Ltd": "Limited",
    "Corp": "Corporation",
}
FIRST_NAMES = [
    "Ada", "Ben", "Cora", "Dev", "Elena", "Femi", "Gus", "Hana", "Ivan",
    "Jun", "Kira", "Leo", "Mina", "Noah", "Oona", "Pablo", "Quinn", "Rosa",
    "Sam", "Tara", "Uma", "Vera", "Wes", "Xena", "Yuri", "Zoe",
]  # fmt: skip
LAST_NAMES = [
    "Alder", "Brook", "Cole", "Dale", "Ellis", "Frost", "Grove", "Hale",
    "Ives", "Jarvis", "Knox", "Lane", "Moss", "Nash", "Oakes", "Park",
    "Reed", "Shaw", "Tate", "Vance", "Wells", "Young",
]  # fmt: skip


def _unique_names(
    rng: random.Random, firsts: list[str], seconds: list[str], count: int
) -> list[str]:
    combos = [(a, b) for a in firsts for b in seconds]
    if count > len(combos):
        raise ValueError("too many names requested")
    picked = rng.sample(combos, count)
    return [f"{a} {b} {rng.choice(SUFFIXES)}" for a, b in picked]


def vendor_names(rng: random.Random, count: int) -> list[str]:
    return _unique_names(rng, VENDOR_PREFIXES, VENDOR_PRODUCTS, count)


def customer_names(rng: random.Random, count: int) -> list[str]:
    return _unique_names(rng, CUSTOMER_PREFIXES, CUSTOMER_INDUSTRIES, count)


def company_name(rng: random.Random) -> str:
    first = rng.choice(COMPANY_PREFIXES)
    second = rng.choice(COMPANY_PRODUCTS)
    return f"{first} {second} {rng.choice(['Co', 'Inc', 'LLC', 'Ltd'])}"


def name_variant(name: str, rng: random.Random) -> str:
    """A punctuation or suffix change of a vendor name."""
    core, suffix = name.rsplit(" ", 1)
    options = [
        f"{core} {suffix}.",
        f"{core}, {suffix}",
        f"{core} {LONG_SUFFIX[suffix]}",
        core,
    ]
    return rng.choice(options)


def person_names(rng: random.Random, count: int) -> list[str]:
    combos = [(a, b) for a in FIRST_NAMES for b in LAST_NAMES]
    if count > len(combos):
        raise ValueError("too many names requested")
    return [f"{a} {b}" for a, b in rng.sample(combos, count)]
