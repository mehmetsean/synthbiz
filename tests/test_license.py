import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"LICENSE", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "tests/test_license.py"}
WORDS = ("Apache", "CC BY", "creativecommons")


def test_license_header():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("Copyright (c) 2026 Mehmet Tuzunkan. All rights reserved.")


def test_pyproject_license():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["license"] == "LicenseRef-Proprietary"
    assert data["project"]["license-files"] == ["LICENSE"]


def test_no_old_license_words():
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    for name in out.split():
        if name in SKIP or name.startswith("docs/adr/0010"):
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for word in WORDS:
            assert word not in text, f"{word} in {name}"


NOTICE = (
    "All rights reserved. You may view the code and run it to evaluate it. "
    "Commercial use needs a paid license from Mehmet Tuzunkan: "
    "https://www.linkedin.com/in/mstuzunkan"
)


def test_readme_notice():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert NOTICE in text.splitlines()
    assert "Outside code contributions are not accepted." in text


def test_io_notice_matches():
    from synthbiz.io import NOTICE as io_notice

    assert io_notice == NOTICE


def test_no_contributing_or_classifiers():
    assert not (ROOT / "CONTRIBUTING.md").exists()
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "classifiers" not in data["project"]
