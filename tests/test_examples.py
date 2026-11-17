from pathlib import Path

from synthbiz.cli import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "seed42-3m"
COMMAND = (
    "synthbiz generate --seed 42 --months 3 --size small "
    "--anomaly-rate 0.04 --out examples/seed42-3m --force"
)


def test_example_is_current(tmp_path: Path) -> None:
    out = tmp_path / "fresh"
    code = main(
        ["generate", "--seed", "42", "--months", "3", "--size", "small"]
        + ["--anomaly-rate", "0.04", "--out", str(out)]
    )
    assert code == 0
    fresh = sorted(p.name for p in out.iterdir())
    committed = sorted(p.name for p in EXAMPLE.iterdir())
    assert fresh == committed, (
        f"File names differ. Missing: {sorted(set(fresh) - set(committed))}. "
        f"Extra: {sorted(set(committed) - set(fresh))}. "
        f"Regenerate with: {COMMAND}"
    )
    for name in fresh:
        assert (out / name).read_bytes() == (EXAMPLE / name).read_bytes(), (
            f"{name} differs from the committed example. Regenerate it with: {COMMAND}"
        )


def test_example_checks_pass(capsys: object) -> None:
    assert main(["check", str(EXAMPLE)]) == 0
