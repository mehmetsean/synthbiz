import re
import tomllib
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
    # YAML quirk
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


def test_pages_runs_on_main_pull_requests_and_by_hand() -> None:
    triggers = _triggers(_load(WORKFLOWS / "pages.yml"))
    assert triggers["push"]["branches"] == ["main"]
    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers


def test_pages_deploy_and_upload_skip_pull_requests() -> None:
    jobs = _load(WORKFLOWS / "pages.yml")["jobs"]
    assert "github.event_name != 'pull_request'" in jobs["deploy"]["if"]
    uploads = [
        step
        for step in jobs["build"]["steps"]
        if "upload-pages-artifact" in step.get("uses", "")
    ]
    assert len(uploads) == 1
    assert "github.event_name != 'pull_request'" in uploads[0]["if"]


def test_pages_build_runs_tests_before_badges_before_upload() -> None:
    steps = _load(WORKFLOWS / "pages.yml")["jobs"]["build"]["steps"]
    texts = [step.get("run", step.get("uses", "")) for step in steps]
    pytest_at = next(i for i, t in enumerate(texts) if t.startswith("pytest"))
    assert "--junitxml" in texts[pytest_at]
    assert "--cov-report=json" in texts[pytest_at]
    badges_at = next(i for i, t in enumerate(texts) if "make_badges.py" in t)
    upload_at = next(i for i, t in enumerate(texts) if "upload-pages-artifact" in t)
    assert pytest_at < badges_at < upload_at


def test_pages_concurrency_is_per_ref() -> None:
    group = _load(WORKFLOWS / "pages.yml")["concurrency"]
    assert "github.ref" in group["group"]
    assert group["cancel-in-progress"] is False


def test_codeql_can_run_by_hand() -> None:
    triggers = _triggers(_load(WORKFLOWS / "codeql.yml"))
    assert "workflow_dispatch" in triggers


def test_browser_job_is_not_required_and_actions_are_pinned() -> None:
    data = _load(WORKFLOWS / "ci.yml")
    assert "browser" in data["jobs"]
    assert data["jobs"]["ci"]["needs"] == "test"
    for path in FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "uses:" in line:
                assert re.search(r"@[0-9a-f]{40} # v\d", line), line


def test_browser_extra_keeps_runtime_dependencies_empty() -> None:
    root = WORKFLOWS.parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"].get("dependencies", []) == []
    assert "playwright" in " ".join(
        project["project"]["optional-dependencies"]["browser"]
    )
