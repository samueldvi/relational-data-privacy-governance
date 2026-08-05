from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from psycopg import Connection, sql

from src.infrastructure.config.loader import load_yaml_path
from src.infrastructure.serialization.json_manifest_repository import JsonManifestRepository
from src.masking_manifest import MANIFEST_PATH

SOURCE_SCHEMAS = ("billing", "crm", "hr")
MASKED_SCHEMAS = ("masked_billing", "masked_crm", "masked_hr")
REGISTRY_PATH = Path("config/pii_registry.yml")


class ProjectStatusProvider:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    @staticmethod
    def _git_branch() -> str:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return "unavailable"
        return result.stdout.strip() or "detached"

    @staticmethod
    def _counts(cursor: Any, schemas: tuple[str, ...]) -> tuple[int, int]:
        cursor.execute(
            """
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE table_type='BASE TABLE' AND table_schema = ANY(%s)
            ORDER BY table_schema, table_name
            """,
            (list(schemas),),
        )
        tables = cursor.fetchall()
        rows = 0
        for schema_name, table_name in tables:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema_name), sql.Identifier(table_name))
            )
            rows += cursor.fetchone()[0]
        return len(tables), rows

    def snapshot(self) -> dict[str, Any]:
        registry_columns = len(load_yaml_path(REGISTRY_PATH).get("columns", [])) if REGISTRY_PATH.is_file() else 0
        manifest = None
        if MANIFEST_PATH.is_file():
            try:
                candidate = JsonManifestRepository(MANIFEST_PATH).load()
                manifest = candidate if candidate.get("final_status") == "success" else None
            except Exception:
                manifest = None
        with self._connect() as connection, connection.cursor() as cursor:
            source_tables, source_rows = self._counts(cursor, SOURCE_SCHEMAS)
            masked_tables, masked_rows = self._counts(cursor, MASKED_SCHEMAS)
        ready = all(
            (
                source_tables == 20,
                masked_tables == 20,
                source_rows == masked_rows and source_rows > 0,
                registry_columns == 109,
                manifest is not None,
            )
        )
        return {
            "postgresql": "reachable",
            "source_schemas": len(SOURCE_SCHEMAS),
            "source_tables": source_tables,
            "source_rows": source_rows,
            "masked_tables": masked_tables,
            "masked_rows": masked_rows,
            "registry": "available" if registry_columns else "missing",
            "registry_columns": registry_columns,
            "manifest": "available" if manifest else "missing_or_invalid",
            "last_validation": "available" if manifest and manifest.get("validations") else "unavailable",
            "branch": self._git_branch(),
            "status": "ready" if ready else "incomplete",
        }
