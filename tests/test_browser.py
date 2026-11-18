import os
import re
from collections.abc import Iterator
from typing import Any

import pytest

URL = os.environ.get("SYNTHBIZ_DEMO_URL", "")

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(not URL, reason="set SYNTHBIZ_DEMO_URL to run"),
]

WIDTHS = [(390, 800), (1366, 900)]
MONEY = re.compile(r"^-?\$\d{1,3}(,\d{3})*\.\d{2}$")
DOLLARS = [
    ("0", "$0.00"),
    ("5", "$0.05"),
    ("-5", "-$0.05"),
    ("99", "$0.99"),
    ("100", "$1.00"),
    ("-1234567", "-$12,345.67"),
    ("999999999999999999", "$9,999,999,999,999,999.99"),
]
HINT_HIDDEN = """() => {
  for (const box of document.querySelectorAll("#tables .table-box")) {
    if (box.querySelector("caption").textContent.startsWith("vendors")) {
      return box.querySelector(".hint").hidden;
    }
  }
}"""


@pytest.fixture(scope="module")
def page() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    errors: list[str] = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1366, "height": 900})
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else 0)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(URL)
        pg.wait_for_function(
            "!document.getElementById('generate').disabled", timeout=120_000
        )
        pg.select_option("#size", "small")
        pg.fill("#months", "3")
        pg.click("#generate")
        pg.wait_for_selector("#results:not([hidden])", timeout=60_000)
        yield pg
        assert errors == []
        browser.close()


def _overflow(page: Any) -> int:
    root = "document.documentElement"
    return int(page.evaluate(f"{root}.scrollWidth - {root}.clientWidth"))


def _resize(page: Any, width: int, height: int) -> None:
    page.set_viewport_size({"width": width, "height": height})


def test_generate_flow(page: Any) -> None:
    assert page.locator("#tables table").count() == 10
    assert page.locator("#summary li").count() == 4
    for text in page.locator("#summary .value").all_inner_texts():
        assert re.match(r"^[\d,]+( of \d+)?$", text)
    marks = page.locator("#checks .mark").all_inner_texts()
    assert marks and all(m == "[PASS]" for m in marks)
    cells = page.locator("#tables td.num").all_inner_texts()
    assert cells and all(MONEY.match(c) for c in cells)
    for width, height in WIDTHS:
        _resize(page, width, height)
        assert _overflow(page) <= 0, width
    _resize(page, 1366, 900)


@pytest.mark.parametrize(("cents", "expected"), DOLLARS)
def test_format_dollars(page: Any, cents: str, expected: str) -> None:
    assert page.evaluate("(v) => formatDollars(v)", cents) == expected


@pytest.mark.parametrize("text", ["", "abc"])
def test_bad_money_value_stays_plain_text(page: Any, text: str) -> None:
    got = page.evaluate("(v) => makeCell(v, true).textContent", text)
    assert got == text
    assert page.evaluate("(v) => makeCell(v, true).className", text) == ""


def test_scroll_hint_follows_width(page: Any) -> None:
    _resize(page, 1366, 900)
    page.wait_for_function(f"({HINT_HIDDEN})() === true")
    _resize(page, 390, 800)
    page.wait_for_function(f"({HINT_HIDDEN})() === false")
    _resize(page, 1366, 900)
    page.wait_for_function(f"({HINT_HIDDEN})() === true")


def test_long_text_toggle_by_keyboard(page: Any) -> None:
    _resize(page, 1366, 900)
    for key in ["Enter", "Space"]:
        summary = page.locator("#labels td.long summary").first
        details = page.locator("#labels td.long details").first
        summary.focus()
        assert page.evaluate("document.activeElement.tagName") == "SUMMARY"
        page.keyboard.press(key)
        assert details.get_attribute("open") is not None
        full = details.locator("p")
        assert full.is_visible()
        assert len(full.inner_text()) > 60
        page.keyboard.press(key)
        assert details.get_attribute("open") is None
