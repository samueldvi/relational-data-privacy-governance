"""Canonical, side-effect-free serialization and checksums."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


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
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def table_checksum(schema_name: str, table_name: str, columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    return hashlib.sha256(canonical_table_payload(schema_name, table_name, columns, rows)).hexdigest()


def finalize_manifest(deterministic: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(deterministic, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**deterministic, "global_checksum": hashlib.sha256(payload).hexdigest()}
