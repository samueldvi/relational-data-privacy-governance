from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def _workflow() -> dict:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_workflow_yaml_is_valid_and_has_stable_names() -> None:
    workflow = _workflow()
    assert workflow["name"] == "CI"
    assert set(workflow["jobs"]) == {"tests"}


def test_workflow_triggers_cover_main_features_and_pull_requests() -> None:
    triggers = _workflow()["on"]
    assert triggers["push"]["branches"] == ["main", "feature/**", "refactor/**"]
    assert triggers["pull_request"]["branches"] == ["main"]
    assert "workflow_dispatch" in triggers


def test_workflow_uses_python_312_and_postgresql_16() -> None:
    job = _workflow()["jobs"]["tests"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["services"]["postgres"]["image"] == "postgres:16"
    setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python"))
    assert setup["with"]["python-version"] == "3.12"


def test_workflow_runs_database_pipeline_tests_and_git_checks() -> None:
    steps = _workflow()["jobs"]["tests"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "psql" in commands and "--set ON_ERROR_STOP=1" in commands
    assert "python -m src.cli all" in commands
    assert "python -m src.cli drift --check" in commands
    assert "python -m pytest tests/contract/test_architecture.py -q" in commands
    assert "pytest -q" in commands
    assert "git diff --check" in commands
    assert "git ls-files" in commands
    assert "python scripts/check_repository_safety.py" in commands


def test_workflow_permissions_are_read_only_and_concurrency_is_enabled() -> None:
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] == "true"
    assert workflow["concurrency"]["group"] == "ci-${{ github.workflow }}-${{ github.ref }}"


def test_workflow_uses_only_explicit_synthetic_test_credentials() -> None:
    workflow = _workflow()
    environment = workflow["jobs"]["tests"]["env"]
    assert set(environment) == {
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "MASKING_SECRET",
    }
    assert "synthetic" in environment["POSTGRES_PASSWORD"]
    assert "synthetic" in environment["MASKING_SECRET"]
    assert len(environment["MASKING_SECRET"]) >= 32
