from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from src.application.pipeline import PIPELINE_PHASES

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_domain_has_no_infrastructure_or_io_framework_dependencies() -> None:
    forbidden = ("src.infrastructure", "src.cli", "psycopg", "argparse", "dotenv", "yaml")
    violations = []
    for path in sorted((SRC / "domain").rglob("*.py")):
        for imported in _imports(path):
            if imported.startswith(forbidden):
                violations.append(f"{path.relative_to(ROOT)} -> {imported}")
    assert violations == []


def test_application_does_not_import_concrete_infrastructure() -> None:
    violations = [
        f"{path.relative_to(ROOT)} -> {imported}"
        for path in sorted((SRC / "application").rglob("*.py"))
        for imported in _imports(path)
        if imported.startswith("src.infrastructure")
    ]
    assert violations == []


def test_cli_does_not_import_database_or_serialization_adapters() -> None:
    forbidden = ("psycopg", "yaml", "src.infrastructure.database", "src.infrastructure.serialization")
    violations = [
        f"{path.relative_to(ROOT)} -> {imported}"
        for path in sorted((SRC / "cli").rglob("*.py"))
        for imported in _imports(path)
        if imported.startswith(forbidden)
    ]
    assert violations == []


def test_python_sources_do_not_hardcode_virtualenv_interpreter() -> None:
    forbidden_interpreter = ".venv/bin/" + "python"
    violations = [
        str(path.relative_to(ROOT))
        for base in (SRC, ROOT / "tests", ROOT / "scripts")
        for path in base.rglob("*.py")
        if forbidden_interpreter in path.read_text(encoding="utf-8")
    ]
    assert violations == []


def test_pipeline_order_has_one_authoritative_definition() -> None:
    assert PIPELINE_PHASES == ("generate", "inventory", "profile", "classify", "mask", "validate")
    occurrences = sum("PIPELINE_PHASES =" in path.read_text(encoding="utf-8") for path in SRC.rglob("*.py"))
    assert occurrences == 1


@pytest.mark.parametrize(
    "command", ("generate", "inventory", "profile", "classify", "mask", "validate", "status", "all")
)
def test_public_cli_commands_remain_compatible(command: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", command, "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
