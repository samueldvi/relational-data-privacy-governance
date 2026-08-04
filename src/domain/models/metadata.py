from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    schema_name: str
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    nullable: bool
    row_count: int = 0
    primary_key: bool = False
    foreign_key: bool = False
    unique: bool = False

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}.{self.column_name}"


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    column: ColumnMetadata
    non_null_count: int
    distinct_count: int
    detected_patterns: tuple[str, ...] = ()
    redacted_sample_count: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
