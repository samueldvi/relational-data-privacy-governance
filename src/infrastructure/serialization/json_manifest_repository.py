from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.shared.errors import ValidationError


class JsonManifestRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValidationError("Masking manifest is unavailable or invalid.") from error
        if not isinstance(document, dict):
            raise ValidationError("Masking manifest must be a JSON object.")
        return document

    def save(self, manifest: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
