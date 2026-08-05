from __future__ import annotations

from typing import Protocol

from src.domain.schema_drift import DriftReport, SchemaSnapshot, compare_schema_snapshots, validate_governance
from src.shared.errors import SchemaDriftError


class SchemaSnapshotProvider(Protocol):
    def snapshot(self) -> SchemaSnapshot: ...


class SchemaBaselineStore(Protocol):
    def load(self) -> SchemaSnapshot: ...
    def save(self, snapshot: SchemaSnapshot) -> None: ...


class SchemaDriftService:
    def __init__(self, current: SchemaSnapshotProvider, baseline: SchemaBaselineStore) -> None:
        self._current = current
        self._baseline = baseline

    def report(self) -> DriftReport:
        return compare_schema_snapshots(self._baseline.load(), self._current.snapshot())

    def write_baseline(self) -> dict[str, int]:
        snapshot = self._current.snapshot()
        governance_issues = validate_governance(snapshot)
        if governance_issues:
            raise SchemaDriftError(f"Baseline update blocked by {len(governance_issues)} governance issue(s).")
        self._baseline.save(snapshot)
        return {
            "schemas": len({table.schema for table in snapshot.tables}),
            "tables": len(snapshot.tables),
            "columns": sum(len(table.columns) for table in snapshot.tables),
            "constraints": sum(len(table.constraints) for table in snapshot.tables),
            "logical_relationships": len(snapshot.logical_relationships),
        }
