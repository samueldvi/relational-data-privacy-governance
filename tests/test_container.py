from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_is_pinned_minimal_and_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    first_line = dockerfile.splitlines()[0]
    assert first_line.startswith("FROM python:3.12.10-slim-bookworm@sha256:")
    assert "USER 10001:10001" in dockerfile
    assert "requirements-runtime.txt" in dockerfile
    assert "requirements-dev.txt" not in dockerfile
    assert "apt-get" not in dockerfile
    assert "MASKING_SECRET" not in dockerfile
    assert "POSTGRES_PASSWORD" not in dockerfile


def test_docker_context_excludes_secrets_caches_tests_and_generated_data() -> None:
    ignored = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    assert {".git", ".env", ".venv", "output", "data/generated", "tests"} <= ignored


def test_compose_pipeline_is_read_only_non_root_and_waits_for_healthy_database() -> None:
    compose = yaml.safe_load((ROOT / "compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["privacy-pipeline"]
    assert service["read_only"] is True
    assert service["user"] == "10001:10001"
    assert service["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert service["environment"]["POSTGRES_HOST"] == "postgres"
    assert service["environment"]["POSTGRES_PORT"] == "5432"
    assert "/tmp:rw,noexec,nosuid,nodev,size=64m" in service["tmpfs"]
    assert "pipeline_output:/app/output" in service["volumes"]


def test_container_ci_builds_scans_and_runs_the_end_to_end_cli() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["container"]["steps"])
    assert "docker compose build privacy-pipeline" in commands
    assert "test ! -e /app/.env" in commands
    assert "python -m src.cli status" in commands
    assert "python -m src.cli all" in commands
    assert "python -m src.cli drift --check" in commands
    assert "python scripts/check_repository_safety.py" in commands
