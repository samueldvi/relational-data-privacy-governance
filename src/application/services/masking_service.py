from __future__ import annotations

from collections.abc import Callable
from typing import Any


class MaskingService:
    def __init__(
        self, apply_masking: Callable[[], dict[str, Any]],
        dry_run: Callable[[], dict[str, Any]],
        validate_only: Callable[[], dict[str, Any]],
    ) -> None:
        self._apply_masking = apply_masking
        self._dry_run = dry_run
        self._validate_only = validate_only

    def run(self, *, dry_run: bool = False, validate_only: bool = False) -> dict[str, Any]:
        if dry_run and validate_only:
            raise ValueError("Masking dry-run and validate-only modes are mutually exclusive.")
        if dry_run:
            return self._dry_run()
        if validate_only:
            result = self._validate_only()
            return {
                "tables": len(result["masked_counts"]),
                "rows": sum(result["masked_counts"].values()),
                "validations": len(result["validations"]),
            }
        return self._apply_masking()
