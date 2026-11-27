import io
import sys
from pathlib import Path

import pytest

from synthbiz.cli import main

COMMANDS = {
    "generate": ["generate", "--months", "1"],
    "workforce": ["workforce", "--days", "1"],
    "project": ["project", "--tasks", "8"],
}


def ascii_stdout(monkeypatch: pytest.MonkeyPatch) -> io.BytesIO:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii", write_through=True)
    monkeypatch.setattr(sys, "stdout", stream)
    return raw


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_non_ascii_out_on_ascii_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    raw = ascii_stdout(monkeypatch)
    out = tmp_path / "caf\u00e9"
    args = [*COMMANDS[command], "--out", str(out)]
    assert main(args) == 0
    assert (out / "manifest.json").is_file()
    assert b"caf\\xe9" in raw.getvalue()
    raw.seek(0)
    raw.truncate()
    # error line
    assert main(args) == 1
    assert raw.getvalue().startswith(b"Error: ")
    assert b"caf\\xe9" in raw.getvalue()


@pytest.mark.parametrize(
    ("folder", "code", "want"),
    [("caf\u00e9", 1, b"Error: folder not found"), ("data", 0, b"All checks")],
)
def test_check_on_ascii_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    folder: str,
    code: int,
    want: bytes,
) -> None:
    assert main([*COMMANDS["generate"], "--out", str(tmp_path / "data")]) == 0
    raw = ascii_stdout(monkeypatch)
    assert main(["check", str(tmp_path / folder)]) == code
    assert want in raw.getvalue()


@pytest.mark.parametrize("command", [*sorted(COMMANDS), "check"])
def test_control_characters_are_escaped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    out = str(tmp_path / "a\x1b\nb\u202e")
    if command == "check":
        assert main(["check", out]) == 1
    else:
        assert main([*COMMANDS[command], "--out", out]) == 0
    printed = capsys.readouterr().out
    assert "a\\x1b\\nb\\u202e" in printed
    assert "\x1b" not in printed and "\u202e" not in printed


def test_printable_text_is_kept_on_utf8(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "caf\u00e9"
    assert main([*COMMANDS["project"], "--out", str(out)]) == 0
    assert str(out) in capsys.readouterr().out
