import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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


class WriteOnly:
    def __init__(self) -> None:
        self.text = ""

    def write(self, text: str) -> int:
        self.text += text
        return len(text)


class NoneEncoding(WriteOnly):
    encoding = None

    def flush(self) -> None:
        pass


class EmptyEncoding(NoneEncoding):
    encoding = ""


class BadWrite(NoneEncoding):
    def write(self, text: str) -> int:
        raise OSError("bad write")


class BadFlush(NoneEncoding):
    def flush(self) -> None:
        raise BrokenPipeError("bad flush")


def closed_stream() -> io.TextIOWrapper:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    stream.close()
    return stream


STREAMS = {
    "none": lambda: None,
    "write_only": WriteOnly,
    "none_encoding": NoneEncoding,
    "empty_encoding": EmptyEncoding,
    "closed": closed_stream,
    "bad_write": BadWrite,
    "bad_flush": BadFlush,
}


@pytest.mark.parametrize("kind", sorted(STREAMS))
@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_unusual_stdout_keeps_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, kind: str
) -> None:
    out = tmp_path / "caf\u00e9"
    args = [*COMMANDS[command], "--out", str(out)]
    monkeypatch.setattr(sys, "stdout", STREAMS[kind]())
    assert main(args) == 0
    assert (out / "manifest.json").is_file()
    monkeypatch.setattr(sys, "stdout", STREAMS[kind]())
    assert main(args) == 1


@pytest.mark.parametrize("kind", sorted(STREAMS))
def test_check_exit_code_on_unusual_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    data = tmp_path / "data"
    assert main([*COMMANDS["generate"], "--out", str(data)]) == 0
    for folder, code in [(data, 0), (tmp_path / "nope", 1)]:
        monkeypatch.setattr(sys, "stdout", STREAMS[kind]())
        assert main(["check", str(folder)]) == code
    (data / "README.txt").write_text("changed", "utf-8")
    monkeypatch.setattr(sys, "stdout", STREAMS[kind]())
    assert main(["check", str(data)]) == 1


@pytest.mark.parametrize("kind", ["write_only", "none_encoding", "empty_encoding"])
def test_stream_without_encoding_gets_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    stream = STREAMS[kind]()
    monkeypatch.setattr(sys, "stdout", stream)
    out = tmp_path / "caf\u00e9"
    assert main([*COMMANDS["generate"], "--out", str(out)]) == 0
    assert isinstance(stream, WriteOnly)
    assert str(out) in stream.text
    assert "listed in labels.csv" in stream.text


def run_broken(kind: str, args: list[str]) -> "subprocess.CompletedProcess[bytes]":
    command = [sys.executable, "-m", "synthbiz", *args]
    options: dict[str, Any] = {"stderr": subprocess.PIPE}
    if kind == "closed":
        return subprocess.run(command, preexec_fn=lambda: os.close(1), **options)
    if kind == "read_only":
        with open(os.devnull, "rb") as f:
            return subprocess.run(command, stdout=f, **options)
    read, write = os.pipe()
    os.close(read)
    try:
        return subprocess.run(command, stdout=write, **options)
    finally:
        os.close(write)


@pytest.mark.skipif(os.name != "posix", reason="posix only")
@pytest.mark.parametrize("kind", ["closed", "read_only", "broken_pipe"])
@pytest.mark.parametrize("command", [*sorted(COMMANDS), "check"])
def test_real_process_with_broken_stdout(
    tmp_path: Path, command: str, kind: str
) -> None:
    out = tmp_path / "data"
    if command == "check":
        assert main([*COMMANDS["generate"], "--out", str(out)]) == 0
        args, again = ["check", str(out)], ["check", str(tmp_path / "nope")]
    else:
        args = again = [*COMMANDS[command], "--out", str(out)]
    for run, code in [(args, 0), (again, 1)]:
        done = run_broken(kind, run)
        assert (done.returncode, done.stderr) == (code, b"")
    assert (out / "manifest.json").is_file()
