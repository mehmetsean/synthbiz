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
