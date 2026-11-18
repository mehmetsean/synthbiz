"""Write coverage.svg and tests.svg from pytest output.

Usage: make_badges.py COVERAGE_JSON JUNIT_XML OUT_DIR

Coverage colors: green at 90 percent or more, yellow at 75 or more, else red.
Test badge is red when any test failed or none ran.
The Pages job runs this script only after pytest passes.
"""

import json
import sys
import xml.etree.ElementTree as ET
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

GREEN = "#1a6b2f"
YELLOW = "#7a5200"
RED = "#b3261e"
LABEL_BG = "#555555"
TEXT = "#ffffff"
FONT = "Verdana, DejaVu Sans, sans-serif"
HEIGHT = 20
PAD = 6

NARROW = set("il.,:;|!'1 ")
WIDE = set("mw%")
NORMAL = set("abcdefghijknopqrstuvxyz023456789,-_")


def char_width(ch: str) -> int:
    if ch in NARROW:
        return 4
    if ch in WIDE:
        return 10
    if ch in NORMAL:
        return 7
    return 8


def text_width(text: str) -> int:
    return sum(char_width(ch) for ch in text)


def truncate(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_DOWN)


def percent_text(value: float) -> str:
    return f"{truncate(value)}%"


def coverage_color(value: float) -> str:
    shown = truncate(value)
    if shown >= 90:
        return GREEN
    if shown >= 75:
        return YELLOW
    return RED


def tests_text(passed: int, failed: int) -> str:
    if failed > 0:
        return f"{passed} passed, {failed} failed"
    if passed == 0:
        return "no tests"
    return f"{passed} passed"


def tests_color(passed: int, failed: int) -> str:
    return RED if failed > 0 or passed == 0 else GREEN


def make_badge(label: str, value: str, color: str) -> str:
    left = text_width(label) + 2 * PAD
    right = text_width(value) + 2 * PAD
    total = left + right
    words = escape(f"{label}: {value}", {'"': "&quot;"})
    label_x = left / 2
    value_x = left + right / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" '
        f'height="{HEIGHT}" role="img" aria-label="{words}">'
        f"<title>{words}</title>"
        f'<rect width="{left}" height="{HEIGHT}" fill="{LABEL_BG}"/>'
        f'<rect x="{left}" width="{right}" height="{HEIGHT}" fill="{color}"/>'
        f'<g fill="{TEXT}" text-anchor="middle" font-family="{FONT}" '
        'font-size="11">'
        f'<text x="{label_x}" y="14">{escape(label)}</text>'
        f'<text x="{value_x}" y="14">{escape(value)}</text>'
        "</g></svg>\n"
    )


def read_coverage(path: Path) -> float:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data["totals"]["percent_covered"])
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise SystemExit(f"cannot read coverage file {path}: {err!r}") from None


def read_tests(path: Path) -> tuple[int, int]:
    try:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        if not suites:
            raise ValueError("no testsuite")
        total = failed = skipped = 0
        for suite in suites:
            total += int(suite.attrib["tests"])
            failed += int(suite.get("failures", "0")) + int(suite.get("errors", "0"))
            skipped += int(suite.get("skipped", "0"))
    except (OSError, ET.ParseError, ValueError, KeyError) as err:
        raise SystemExit(f"cannot read junit file {path}: {err!r}") from None
    return total - failed - skipped, failed


def main(args: list[str]) -> int:
    if len(args) != 3:
        raise SystemExit("usage: make_badges.py COVERAGE_JSON JUNIT_XML OUT_DIR")
    coverage = read_coverage(Path(args[0]))
    passed, failed = read_tests(Path(args[1]))
    out = Path(args[2])
    out.mkdir(parents=True, exist_ok=True)
    cov_svg = make_badge("coverage", percent_text(coverage), coverage_color(coverage))
    test_svg = make_badge("tests", tests_text(passed, failed), tests_color(passed, failed))
    (out / "coverage.svg").write_text(cov_svg, encoding="utf-8")
    (out / "tests.svg").write_text(test_svg, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
