import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "reproduce_readme", ROOT / "scripts" / "reproduce_readme.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_block_has_expected_facts() -> None:
    block = load().build_block()
    assert "seed 42" in block
    assert "Total rows:" in block
    assert "manifest.json sha256:" in block
    assert "PASS" in block


def test_block_is_repeatable() -> None:
    mod = load()
    assert mod.build_block() == mod.build_block()


def test_project_lines_by_hand() -> None:
    assert load().project_lines() == [
        "",
        "Project example: seed 42, 50 tasks.",
        "",
        "- tasks: 50",
        "- summary tasks: 3",
        "- milestones: 3",
        "- links: 75",
        "- FS links: 65",
        "- SS links: 7",
        "- FF links: 2",
        "- SF links: 1",
        "- positive lags: 11",
        "- negative lags: 2",
        "- holiday exceptions: 43",
        "- holidays listed through year: 2028",
        "- ranges: 44",
        "- risks: 3",
        "- same seed gives same bytes: PASS",
        "- task limit: 8 to 5000",
        "- start date limit: 2000-01-01 to 2099-12-31",
        "- links at the task limit: 9470",
        "- risks at the task limit: 200",
    ]


def test_replace_block() -> None:
    mod = load()
    text = "a\n<!-- numbers:start -->\nold\n<!-- numbers:end -->\nb\n"
    out = mod.replace_block(text, "new")
    assert out == "a\n<!-- numbers:start -->\nnew\n<!-- numbers:end -->\nb\n"


def test_replace_block_needs_markers() -> None:
    with pytest.raises(ValueError):
        load().replace_block("no markers", "x")


def test_check_and_write(tmp_path: Path) -> None:
    mod = load()
    readme = tmp_path / "README.md"
    readme.write_text("x\n<!-- numbers:start -->\nold\n<!-- numbers:end -->\n")
    assert mod.main(["--check", "--readme", str(readme)]) == 1
    assert mod.main(["--readme", str(readme)]) == 0
    assert mod.main(["--check", "--readme", str(readme)]) == 0
