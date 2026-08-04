"""Deterministic checksums and manifest serialization for masked datasets."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("output/masking_manifest.json")


def canonical_value(value: Any) -> Any:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": format(value, "f")}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat(timespec="microseconds")}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, int):
        return {"type": "integer", "value": value}
    if isinstance(value, float):
        return {"type": "float", "value": format(value, ".17g")}
    return {"type": "string", "value": str(value)}


def canonical_table_payload(
    schema_name: str, table_name: str, columns: list[str], rows: list[tuple[Any, ...]]
) -> bytes:
    document = {
        "schema_name": schema_name,
        "table_name": table_name,
        "columns": columns,
        "rows": [[canonical_value(value) for value in row] for row in rows],
    }
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def table_checksum(
    schema_name: str, table_name: str, columns: list[str], rows: list[tuple[Any, ...]]
) -> str:
    return hashlib.sha256(
        canonical_table_payload(schema_name, table_name, columns, rows)
    ).hexdigest()


def current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def finalize_manifest(deterministic: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(
        deterministic, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    document = dict(deterministic)
    document["global_checksum"] = hashlib.sha256(payload).hexdigest()
    return document


def write_manifest(
    manifest: dict[str, Any], path: Path = MANIFEST_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
