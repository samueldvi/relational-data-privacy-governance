from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.shared.errors import ValidationError


class ValidationService:
    def __init__(
        self, validate_masked: Callable[[], dict[str, Any]],
        load_manifest: Callable[[], dict[str, Any]],
        apply_to_path: Callable[[Path], dict[str, Any]],
    ) -> None:
        self._validate_masked = validate_masked
        self._load_manifest = load_manifest
        self._apply_to_path = apply_to_path

    def run(self, *, check_idempotence: bool = False) -> dict[str, Any]:
        result = self._validate_masked()
        manifest = self._load_manifest()
        if manifest.get("table_checksums") != result["table_checksums"]:
            raise ValidationError("Manifest checksums do not match the current masked state.")
        idempotent = None
        if check_idempotence:
            with TemporaryDirectory(prefix="privacy-governance-validation-") as directory:
                first = self._apply_to_path(Path(directory) / "first.json")
                second = self._apply_to_path(Path(directory) / "second.json")
            idempotent = first == second
            if not idempotent:
                raise ValidationError("Equivalent masking executions are not deterministic.")
        return {
            "tables": len(result["masked_counts"]),
            "rows": sum(result["masked_counts"].values()),
            "validations": len(result["validations"]),
            "checksum": manifest["global_checksum"], "idempotent": idempotent,
        }
