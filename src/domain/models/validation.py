from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationResult:
    tables: int
    rows: int
    checks: tuple[str, ...]
    table_checksums: tuple[tuple[str, str], ...] = ()
    global_checksum: str | None = None
    idempotent: bool | None = None

    @property
    def successful(self) -> bool:
        return self.tables > 0 and self.rows >= 0 and bool(self.checks)
