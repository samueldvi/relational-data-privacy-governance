"""Deterministic checksums and manifest serialization for masked datasets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.domain.validation.manifest import (
    canonical_table_payload,
    canonical_value,
    finalize_manifest,
    table_checksum,
)

MANIFEST_PATH = Path("output/masking_manifest.json")

__all__ = [
    "canonical_table_payload",
    "canonical_value",
    "finalize_manifest",
    "table_checksum",
]


def current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def write_manifest(manifest: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
