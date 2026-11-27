import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "make_badges", ROOT / "scripts" / "make_badges.py"
)
assert spec is not None and spec.loader is not None
mb = importlib.util.module_from_spec(spec)
sys.modules["make_badges"] = mb
spec.loader.exec_module(mb)

SVG = "{http://www.w3.org/2000/svg}"


def write_cov(path: Path, percent: float) -> Path:
    path.write_text(json.dumps({"totals": {"percent_covered": percent}}))
    return path


def write_junit(path: Path, tests: int, failures: int = 0, skipped: int = 0) -> Path:
    path.write_text(
        '<?xml version="1.0"?><testsuites>'
        f'<testsuite tests="{tests}" failures="{failures}" errors="0" '
        f'skipped="{skipped}"/></testsuites>'
    )
    return path


def luminance(color: str) -> float:
    parts = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_read_coverage(tmp_path: Path) -> None:
    assert mb.read_coverage(write_cov(tmp_path / "c.json", 99.46)) == 99.46


def test_read_tests_counts_passed(tmp_path: Path) -> None:
    path = write_junit(tmp_path / "j.xml", 10, failures=1, skipped=2)
    assert mb.read_tests(path) == (7, 1)


def test_read_tests_single_testsuite_root(tmp_path: Path) -> None:
    path = tmp_path / "j.xml"
    path.write_text('<testsuite tests="4" failures="0" errors="1" skipped="0"/>')
    assert mb.read_tests(path) == (3, 1)


def test_percent_text_one_decimal() -> None:
    assert mb.percent_text(99.46) == "99.4%"
    assert mb.percent_text(100) == "100.0%"
    assert mb.percent_text(0) == "0.0%"


@pytest.mark.parametrize(
    ("value", "text", "color"),
    [
        (99.95, "99.9%", mb.GREEN),
        (99.99, "99.9%", mb.GREEN),
        (100, "100.0%", mb.GREEN),
        (89.96, "89.9%", mb.YELLOW),
        (74.96, "74.9%", mb.RED),
    ],
)
def test_coverage_never_rounds_up(value: float, text: str, color: str) -> None:
    assert mb.percent_text(value) == text
    assert mb.coverage_color(value) == color


@pytest.mark.parametrize(
    ("value", "color"),
    [
        (100, mb.GREEN),
        (90, mb.GREEN),
        (89.9, mb.YELLOW),
        (75, mb.YELLOW),
        (74.9, mb.RED),
        (0, mb.RED),
    ],
)
def test_coverage_color_thresholds(value: float, color: str) -> None:
    assert mb.coverage_color(value) == color


def test_tests_text() -> None:
    assert mb.tests_text(258, 0) == "258 passed"
    assert mb.tests_text(250, 8) == "250 passed, 8 failed"
    assert mb.tests_text(0, 0) == "no tests"


def test_failed_tests_are_red() -> None:
    assert mb.tests_color(5, 0) == mb.GREEN
    assert mb.tests_color(5, 1) == mb.RED


def test_zero_tests_is_red_no_tests(tmp_path: Path) -> None:
    junit = write_junit(tmp_path / "j.xml", 0)
    assert mb.read_tests(junit) == (0, 0)
    assert mb.tests_color(0, 0) == mb.RED
    cov = write_cov(tmp_path / "c.json", 95)
    mb.main([str(cov), str(junit), str(tmp_path / "out")])
    svg = (tmp_path / "out" / "tests.svg").read_text()
    assert "no tests" in svg
    assert mb.RED in svg


def test_two_testsuites_are_summed(tmp_path: Path) -> None:
    path = tmp_path / "j.xml"
    path.write_text(
        "<testsuites>"
        '<testsuite tests="3" failures="1" errors="0" skipped="0"/>'
        '<testsuite tests="5" failures="0" errors="1" skipped="1"/>'
        "</testsuites>"
    )
    assert mb.read_tests(path) == (5, 2)


def test_testsuites_without_children(tmp_path: Path) -> None:
    path = tmp_path / "j.xml"
    path.write_text("<testsuites/>")
    with pytest.raises(SystemExit) as err:
        mb.read_tests(path)
    assert "j.xml" in str(err.value)


def test_testsuite_without_tests_attribute(tmp_path: Path) -> None:
    path = tmp_path / "j.xml"
    path.write_text('<testsuite failures="0"/>')
    with pytest.raises(SystemExit) as err:
        mb.read_tests(path)
    assert "j.xml" in str(err.value)


def test_char_widths() -> None:
    assert mb.char_width("i") == 4
    assert mb.char_width("m") == 10
    assert mb.char_width("a") == 7
    assert mb.char_width("A") == 8
    assert mb.char_width("\u00e9") == 8


def test_exact_total_widths() -> None:
    cov = ET.fromstring(mb.make_badge("coverage", "99.5%", mb.GREEN))
    assert cov.get("width") == "115"
    tests = ET.fromstring(mb.make_badge("tests", "285 passed", mb.GREEN))
    assert tests.get("width") == "126"
    rects = tests.findall(f"{SVG}rect")
    assert rects[0].get("width") == "47"
    assert rects[1].get("x") == "47"
    assert rects[1].get("width") == "79"


def test_quote_is_escaped_in_label_and_title() -> None:
    svg = mb.make_badge('a"b', "x", mb.GREEN)
    root = ET.fromstring(svg)
    assert 'aria-label="a&quot;b: x"' in svg
    assert "<title>a&quot;b: x</title>" in svg
    assert root.get("aria-label") == 'a"b: x'


def test_contrast_ratios() -> None:
    for color in (mb.GREEN, mb.YELLOW, mb.RED, mb.LABEL_BG):
        assert contrast(color, mb.TEXT) >= 4.5


def test_text_is_escaped() -> None:
    svg = mb.make_badge('a<b>&"', "x<y", mb.GREEN)
    ET.fromstring(svg)
    assert "<b>" not in svg
    assert "a&lt;b&gt;&amp;" in svg


def test_same_input_same_bytes() -> None:
    assert mb.make_badge("tests", "5 passed", mb.GREEN) == mb.make_badge(
        "tests", "5 passed", mb.GREEN
    )


def test_width_grows_with_text() -> None:
    assert mb.text_width("100.0%") > mb.text_width("1%")


def test_svg_has_accessibility_parts() -> None:
    root = ET.fromstring(mb.make_badge("coverage", "99.5%", mb.GREEN))
    assert root.get("role") == "img"
    assert root.get("aria-label") == "coverage: 99.5%"
    assert root.findtext(f"{SVG}title") == "coverage: 99.5%"
    assert len(root.findall(f"{SVG}rect")) == 2


def test_main_writes_both_files(tmp_path: Path) -> None:
    cov = write_cov(tmp_path / "c.json", 99.5)
    junit = write_junit(tmp_path / "j.xml", 258)
    out = tmp_path / "out"
    assert mb.main([str(cov), str(junit), str(out)]) == 0
    assert "99.5%" in (out / "coverage.svg").read_text()
    assert "258 passed" in (out / "tests.svg").read_text()


def test_missing_file_is_one_line_error(tmp_path: Path) -> None:
    junit = write_junit(tmp_path / "j.xml", 1)
    with pytest.raises(SystemExit) as err:
        mb.main([str(tmp_path / "none.json"), str(junit), str(tmp_path)])
    assert "\n" not in str(err.value)
    assert "none.json" in str(err.value)


@pytest.mark.parametrize("bad", ["not json", "{}", '{"totals": {}}', "[]"])
def test_malformed_coverage(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "c.json"
    path.write_text(bad)
    with pytest.raises(SystemExit) as err:
        mb.read_coverage(path)
    assert "c.json" in str(err.value)


@pytest.mark.parametrize("bad", ["not xml", "<a/>", '<testsuite tests="x"/>'])
def test_malformed_junit(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "j.xml"
    path.write_text(bad)
    with pytest.raises(SystemExit) as err:
        mb.read_tests(path)
    assert "j.xml" in str(err.value)


@given(
    st.floats(min_value=0, max_value=100, allow_nan=False),
    st.integers(min_value=0, max_value=10**7),
)
def test_any_values_give_valid_svg(percent: float, count: int) -> None:
    for label, text, color in (
        ("coverage", mb.percent_text(percent), mb.coverage_color(percent)),
        ("tests", mb.tests_text(count, 0), mb.tests_color(count, 0)),
    ):
        root = ET.fromstring(mb.make_badge(label, text, color))
        assert root.get("aria-label") == f"{label}: {text}"
        least = mb.text_width(label) + mb.text_width(text) + 4 * mb.PAD
        assert int(root.get("width", "0")) >= least


def test_deeply_nested_coverage_file(tmp_path: Path) -> None:
    path = tmp_path / "coverage.json"
    path.write_text("[" * 200_000 + "]" * 200_000, encoding="utf-8")
    with pytest.raises(SystemExit, match=re.escape("cannot read coverage file")):
        mb.read_coverage(path)


@pytest.mark.parametrize("value", ["", "  "])
def test_empty_output_folder(value: str) -> None:
    with pytest.raises(SystemExit, match=re.escape("usage: make_badges.py")):
        mb.main(["coverage.json", "junit.xml", value])
