from pathlib import Path

import yaml


def test_dependabot_covers_python_container_and_actions() -> None:
    config = yaml.safe_load(Path(".github/dependabot.yml").read_text(encoding="utf-8"))
    assert {item["package-ecosystem"] for item in config["updates"]} == {"pip", "docker", "github-actions"}
    assert all(item["schedule"]["interval"] == "weekly" for item in config["updates"])


def test_security_workflow_has_minimal_permissions_and_required_controls() -> None:
    workflow = yaml.load(Path(".github/workflows/security.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"dependencies", "codeql", "container"}
    commands = Path(".github/workflows/security.yml").read_text(encoding="utf-8")
    for required in ("pip-audit", "cyclonedx-py", "codeql-action", "trivy-action", "check_repository_safety.py"):
        assert required in commands
    assert "ignore-unfixed: true" in commands
    assert "severity: CRITICAL,HIGH" in commands


def test_security_policy_forbids_sensitive_report_content_and_makes_no_sla_promise() -> None:
    policy = Path("SECURITY.md").read_text(encoding="utf-8")
    for required in (
        "Versioni supportate",
        "Segnalazione",
        "Scope e limiti",
        "Non esiste una promessa di",
        "dati reali",
    ):
        assert required in policy
