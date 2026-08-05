from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_repository_safety import scan_files


def test_current_repository_passes_safety_check() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_repository_safety.py"],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert "0 violations" in result.stdout


@pytest.mark.parametrize(
    "name,content,reason",
    [
        (".env", "MASKING_SECRET=actual-value", "sensitive filename"),
        ("backup.dump", "binary-ish", "sensitive filename"),
        ("credentials.json", "{}", "sensitive filename"),
        ("output/pii_mapping.json", "{}", "generated or mapping output"),
        ("config.yml", "POSTGRES_PASSWORD: real-unapproved-value", "credential assignment"),
        ("connection.txt", "postgresql" + "://user:secret@db.example/test", "PostgreSQL DSN"),
        ("private.pem", "-----BEGIN " + "PRIVATE KEY-----", "sensitive filename"),
        ("editor.swp", "temporary", "sensitive filename"),
    ],
)
def test_scanner_rejects_sensitive_names_and_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, content: str, reason: str
) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    violations = scan_files([path])
    assert violations
    assert any(reason.casefold() in violation_reason.casefold() for _, violation_reason in violations)


def test_scanner_rejects_current_environment_secret_without_printing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    secret = "isolated-runtime-secret-123456789"
    path = Path("ordinary.txt")
    path.write_text(f"value={secret}", encoding="utf-8")
    violations = scan_files([path], known_values=[secret])
    assert violations == [("ordinary.txt", "current environment secret is tracked")]
    assert secret not in repr(violations)


def test_scanner_allows_documentation_words_placeholders_and_ci_synthetic_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path("documentation.md")
    path.write_text(
        "Discuss password rotation.\n"
        "POSTGRES_PASSWORD=change_me\n"
        "MASKING_SECRET=ci-only-synthetic-secret-not-for-production\n",
        encoding="utf-8",
    )
    assert scan_files([path]) == []


def test_env_is_not_tracked_and_no_database_dump_is_versioned() -> None:
    files = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.splitlines()
    assert ".env" not in files
    assert not any(path.endswith((".dump", ".sql.gz", ".pem", ".key", ".p12")) for path in files)


def test_clean_environment_script_is_bounded_and_non_destructive_by_default() -> None:
    script = Path("scripts/validate_clean_environment.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    assert "--reset" in script and "docker compose down --volumes" in script
    assert "python -m src.cli all" in script
    assert "python -m pytest -q" in script
    assert "scripts/check_repository_safety.py" in script
    assert "git diff --check" in script
    assert "rm -rf" not in script and "docker volume prune" not in script
