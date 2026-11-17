from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
FILES = sorted(WORKFLOWS.glob("*.yml"))


def _load(path: Path) -> dict[Any, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _triggers(data: dict[Any, Any]) -> dict[Any, Any]:
    # YAML 1.1 reads the key "on" as True
    triggers = data.get("on", data.get(True))
    assert isinstance(triggers, dict)
    return triggers


def test_workflow_files_found() -> None:
    names = {path.name for path in FILES}
    assert {"ci.yml", "codeql.yml", "pages.yml"} <= names


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_workflow_parses(path: Path) -> None:
    data = _load(path)
    assert _triggers(data)
    jobs = data.get("jobs")
    assert isinstance(jobs, dict) and jobs
    for job in jobs.values():
        for step in job.get("steps", []):
            assert isinstance(step, dict)
            assert "run" in step or "uses" in step
            if "run" in step:
                assert isinstance(step["run"], str)


def test_pages_runs_on_main_and_by_hand() -> None:
    triggers = _triggers(_load(WORKFLOWS / "pages.yml"))
    assert triggers["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in triggers


def test_codeql_can_run_by_hand() -> None:
    triggers = _triggers(_load(WORKFLOWS / "codeql.yml"))
    assert "workflow_dispatch" in triggers
