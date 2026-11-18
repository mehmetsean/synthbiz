import os
import re
from typing import Any

import pytest

URL = os.environ.get("SYNTHBIZ_DEMO_URL", "")

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(not URL, reason="set SYNTHBIZ_DEMO_URL to run"),
]

WIDTHS = [(390, 800), (1366, 900)]
MONEY = re.compile(r"^-?\$\d{1,3}(,\d{3})*\.\d{2}$")


def _overflow(page: Any) -> int:
    root = "document.documentElement"
    return int(page.evaluate(f"{root}.scrollWidth - {root}.clientWidth"))


def test_generate_flow() -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    errors: list[str] = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else 0)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_function(
            "!document.getElementById('generate').disabled", timeout=120_000
        )
        page.select_option("#size", "small")
        page.fill("#months", "3")
        page.click("#generate")
        page.wait_for_selector("#results:not([hidden])", timeout=60_000)
        assert page.locator("#tables table").count() == 10
        assert page.locator("#summary li").count() == 4
        for text in page.locator("#summary .value").all_inner_texts():
            assert re.match(r"^[\d,]+( of \d+)?$", text)
        marks = page.locator("#checks .mark").all_inner_texts()
        assert marks and all(m == "[PASS]" for m in marks)
        cells = page.locator("#tables td.num").all_inner_texts()
        assert cells and all(MONEY.match(c) for c in cells)
        for width, height in WIDTHS:
            page.set_viewport_size({"width": width, "height": height})
            assert _overflow(page) <= 0, width
        browser.close()
    assert errors == []
