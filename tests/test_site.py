import re
from pathlib import Path

import synthbiz.demo

SITE = Path(__file__).resolve().parent.parent / "site"
PYODIDE = re.compile(r"https://cdn\.jsdelivr\.net/pyodide/v\d+\.\d+\.\d+/full/")


def _html() -> str:
    return (SITE / "index.html").read_text(encoding="utf-8")


def test_pinned_pyodide_with_integrity() -> None:
    html = _html()
    tag = re.search(r"<script[^>]*pyodide\.js[^>]*>", html)
    assert tag is not None
    assert PYODIDE.search(tag.group(0))
    assert re.search(r'integrity="sha384-[A-Za-z0-9+/]{64}"', tag.group(0))
    assert 'crossorigin="anonymous"' in tag.group(0)


def test_app_uses_same_pyodide_version() -> None:
    html = _html()
    js = (SITE / "app.js").read_text(encoding="utf-8")
    page = PYODIDE.search(html)
    app = PYODIDE.search(js)
    assert page is not None and app is not None
    assert page.group(0) == app.group(0)


CSP = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net 'wasm-unsafe-eval' 'unsafe-eval'; "
    "connect-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'"
)


def test_csp_exact_string() -> None:
    assert f'content="{CSP}"' in _html()


def test_csp_meta_tag() -> None:
    html = _html()
    assert 'http-equiv="Content-Security-Policy"' in html
    for part in [
        "default-src 'none'",
        "script-src 'self' https://cdn.jsdelivr.net 'wasm-unsafe-eval'",
        "connect-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
    ]:
        assert part in html


SVG_NS = "http://www.w3.org/2000/svg"


def test_no_other_external_origins() -> None:
    for name in ["index.html", "app.js", "style.css"]:
        text = (SITE / name).read_text(encoding="utf-8").replace(SVG_NS, "")
        origins = set(re.findall(r"https?://[^/\s\"'<>);]+", text))
        assert origins <= {
            "https://cdn.jsdelivr.net",
            "https://github.com",
            "https://www.linkedin.com",
        }, f"{name}: {origins}"


def test_svg_namespace_only_in_app_js() -> None:
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert js.count(SVG_NS) == 1
    for name in ["index.html", "style.css"]:
        assert SVG_NS not in (SITE / name).read_text(encoding="utf-8")


def test_no_inline_handlers_or_innerhtml() -> None:
    assert "innerHTML" not in (SITE / "app.js").read_text(encoding="utf-8")
    html = _html()
    assert not re.search(r"\son\w+=", html)
    assert "<style" not in html


def test_app_calls_existing_demo_functions() -> None:
    js = (SITE / "app.js").read_text(encoding="utf-8")
    names = set(re.findall(r"\bdemo\.(\w+)\(", js))
    assert names
    for name in names:
        assert callable(getattr(synthbiz.demo, name))


def test_pages_workflow_is_pinned_and_gated() -> None:
    root = Path(__file__).resolve().parent.parent
    text = (root / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert text.count("!github.event.repository.private") == 2
    for line in text.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40} # v\d", line), line


def test_no_inline_style_attributes() -> None:
    assert not re.search(r"\sstyle=", _html())
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert 'setAttribute("style"' not in js
    assert ".style." not in js


FOOTER_SENTENCES = [  # noqa: E501
    "This page loads Pyodide (MPL-2.0) and micropip (MPL-2.0) from cdn.jsdelivr.net at runtime. They are not bundled in this repo.",  # noqa: E501
    "Synthetic data for testing and learning only. Any match with a real business is unintended. Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance.",  # noqa: E501
    "Copyright (c) 2026 Mehmet Tuzunkan. All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan",  # noqa: E501
]


def test_footer_sentences_present() -> None:
    footer = _html().split("<footer>")[1].split("</footer>")[0]
    for sentence in FOOTER_SENTENCES:
        assert sentence in footer


def test_privacy_note_present() -> None:
    assert "All data stays in your browser." in _html()
    assert "You can check this in the browser's Network tab." in _html()


def test_css_has_tokens_and_dark_theme() -> None:
    css = (SITE / "style.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
    assert "--color-bg" in css and "--space-3" in css and "--radius" in css


def test_chart_is_accessible_svg() -> None:
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert "createElementNS" in js
    assert '"role", "img"' in js
    assert '"title"' in js and '"desc"' in js


def test_single_source_link_in_header() -> None:
    html = _html()
    assert html.count("Source code on GitHub") == 1
    header = html.split("<header>")[1].split("</header>")[0]
    assert "https://github.com/mehmetsean/synthbiz" in header


def test_money_formatting_and_scroll_hint_in_app() -> None:
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert "function formatDollars" in js
    assert "t.money" in js
    assert "Scroll sideways to see all columns." in js
    assert "<details" not in js and '"details"' in js and '"summary"' in js


def test_css_right_aligns_money_and_wraps_text() -> None:
    css = (SITE / "style.css").read_text(encoding="utf-8")
    assert "td.num" in css and "text-align: right" in css
    assert "overflow-wrap: anywhere" in css
    assert "scrollbar-color" in css
