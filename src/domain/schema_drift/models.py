from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DriftKind(StrEnum):
    BREAKING = "breaking"
    NON_BREAKING = "non-breaking"
    GOVERNANCE = "governance"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True, order=True)
class ColumnSnapshot:
    ordinal_position: int
    name: str
    data_type: str
    udt_name: str
    nullable: bool
    classification: str | None
    masking_rule: str | None
    consistency_group: str | None


@dataclass(frozen=True, slots=True, order=True)
class ConstraintSnapshot:
    kind: str
    name: str
    columns: tuple[str, ...]
    definition: str
    target_schema: str | None = None
    target_table: str | None = None
    target_columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, order=True)
class TableSnapshot:
    schema: str
    name: str
    columns: tuple[ColumnSnapshot, ...]
    constraints: tuple[ConstraintSnapshot, ...]

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True, slots=True, order=True)
class LogicalRelationshipSnapshot:
    source: str
    target: str
    status: str


@dataclass(frozen=True, slots=True, order=True)
class ConsistencyGroupSnapshot:
    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    version: int
    tables: tuple[TableSnapshot, ...]
    logical_relationships: tuple[LogicalRelationshipSnapshot, ...]
    masking_rules: tuple[str, ...]
    consistency_groups: tuple[ConsistencyGroupSnapshot, ...]


@dataclass(frozen=True, slots=True, order=True)
class DriftItem:
    path: str
    kind: DriftKind
    severity: Severity
    message: str
    remediation: str


@dataclass(frozen=True, slots=True)
class DriftReport:
    items: tuple[DriftItem, ...]

    @property
    def has_drift(self) -> bool:
        return bool(self.items)

    def count(self, kind: DriftKind) -> int:
        return sum(item.kind is kind for item in self.items)
