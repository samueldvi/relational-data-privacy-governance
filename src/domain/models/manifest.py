from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.masking_rule import MaskingStatistics


@dataclass(frozen=True, slots=True)
class TableManifest:
    table_name: str
    source_rows: int
    masked_rows: int
    checksum: str


@dataclass(frozen=True, slots=True)
class MaskingManifest:
    format_version: int
    algorithm: str
    tables: tuple[TableManifest, ...]
    load_order: tuple[str, ...]
    validations: tuple[str, ...]
    global_checksum: str
    final_status: str
    statistics: MaskingStatistics = MaskingStatistics()

    @property
    def total_rows(self) -> int:
        return sum(table.masked_rows for table in self.tables)
