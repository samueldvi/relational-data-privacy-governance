from __future__ import annotations

from collections.abc import Iterable

from src.domain.schema_drift.models import (
    DriftItem,
    DriftKind,
    DriftReport,
    SchemaSnapshot,
    Severity,
    TableSnapshot,
)


def _item(
    path: str,
    kind: DriftKind,
    severity: Severity,
    message: str,
    remediation: str,
) -> DriftItem:
    return DriftItem(path, kind, severity, message, remediation)


def validate_governance(snapshot: SchemaSnapshot) -> tuple[DriftItem, ...]:
    rules = set(snapshot.masking_rules)
    groups = {group.name: set(group.columns) for group in snapshot.consistency_groups}
    issues: list[DriftItem] = []
    for table in snapshot.tables:
        for column in table.columns:
            path = f"{table.qualified_name}.{column.name}"
            if not column.classification:
                issues.append(
                    _item(
                        path,
                        DriftKind.GOVERNANCE,
                        Severity.CRITICAL,
                        "Column is not classified.",
                        "Classify the column in the Privacy Metadata Registry before approval.",
                    )
                )
            if not column.masking_rule:
                issues.append(
                    _item(
                        path,
                        DriftKind.GOVERNANCE,
                        Severity.CRITICAL,
                        "Column has no masking rule.",
                        "Assign and review a masking rule before running the masked pipeline.",
                    )
                )
            elif column.masking_rule not in rules:
                issues.append(
                    _item(
                        path,
                        DriftKind.GOVERNANCE,
                        Severity.CRITICAL,
                        f"Masking rule '{column.masking_rule}' is not defined.",
                        "Define the rule or select an existing approved masking rule.",
                    )
                )
            if column.consistency_group and (
                column.consistency_group not in groups or path not in groups[column.consistency_group]
            ):
                issues.append(
                    _item(
                        path,
                        DriftKind.GOVERNANCE,
                        Severity.HIGH,
                        f"Consistency group '{column.consistency_group}' is invalid for the column.",
                        "Align the registry and consistency-group membership.",
                    )
                )
    return tuple(issues)


def _compare_columns(baseline: TableSnapshot, current: TableSnapshot) -> Iterable[DriftItem]:
    baseline_columns = {column.name: column for column in baseline.columns}
    current_columns = {column.name: column for column in current.columns}
    table_path = baseline.qualified_name
    for name in sorted(baseline_columns.keys() - current_columns.keys()):
        yield _item(
            f"{table_path}.{name}",
            DriftKind.BREAKING,
            Severity.HIGH,
            "Approved column was removed.",
            "Restore the column or record and approve an explicit removal decision.",
        )
    for name in sorted(current_columns.keys() - baseline_columns.keys()):
        column = current_columns[name]
        yield _item(
            f"{table_path}.{name}",
            DriftKind.NON_BREAKING if column.classification and column.masking_rule else DriftKind.GOVERNANCE,
            Severity.MEDIUM if column.classification and column.masking_rule else Severity.CRITICAL,
            "New classified column is not in the baseline."
            if column.classification and column.masking_rule
            else "New column is not classified or has no masking rule.",
            "Review the new column and explicitly update the baseline."
            if column.classification and column.masking_rule
            else "Classify the column, assign a masking rule, then update the baseline explicitly.",
        )
    for name in sorted(baseline_columns.keys() & current_columns.keys()):
        expected, actual = baseline_columns[name], current_columns[name]
        path = f"{table_path}.{name}"
        if expected.ordinal_position != actual.ordinal_position:
            yield _item(
                path,
                DriftKind.BREAKING,
                Severity.HIGH,
                f"Column order changed from {expected.ordinal_position} to {actual.ordinal_position}.",
                "Restore the approved order or review downstream positional consumers and update the baseline.",
            )
        if (expected.data_type, expected.udt_name) != (actual.data_type, actual.udt_name):
            yield _item(
                path,
                DriftKind.BREAKING,
                Severity.HIGH,
                f"Type changed from {expected.data_type}/{expected.udt_name} to {actual.data_type}/{actual.udt_name}.",
                "Restore the approved type or assess compatibility and update the baseline explicitly.",
            )
        if expected.nullable != actual.nullable:
            yield _item(
                path,
                DriftKind.BREAKING,
                Severity.HIGH,
                f"Nullability changed from {expected.nullable} to {actual.nullable}.",
                "Review data-quality and loading impact before updating the baseline.",
            )
        for field, label in (
            ("classification", "classification"),
            ("masking_rule", "masking rule"),
            ("consistency_group", "consistency group"),
        ):
            if getattr(expected, field) != getattr(actual, field):
                yield _item(
                    path,
                    DriftKind.GOVERNANCE,
                    Severity.HIGH,
                    f"Approved {label} changed.",
                    f"Review and approve the {label} change before updating the baseline.",
                )


def _compare_constraints(baseline: TableSnapshot, current: TableSnapshot) -> Iterable[DriftItem]:
    expected = {(constraint.kind, constraint.name): constraint for constraint in baseline.constraints}
    actual = {(constraint.kind, constraint.name): constraint for constraint in current.constraints}
    for key in sorted(expected.keys() - actual.keys()):
        constraint = expected[key]
        yield _item(
            f"{baseline.qualified_name}.{constraint.name}",
            DriftKind.BREAKING,
            Severity.HIGH,
            f"Approved {constraint.kind} constraint was removed.",
            "Restore the constraint or approve the integrity change before updating the baseline.",
        )
    for key in sorted(actual.keys() - expected.keys()):
        constraint = actual[key]
        yield _item(
            f"{baseline.qualified_name}.{constraint.name}",
            DriftKind.NON_BREAKING,
            Severity.LOW,
            f"New {constraint.kind} constraint is not in the baseline.",
            "Review compatibility and update the baseline explicitly.",
        )
    for key in sorted(expected.keys() & actual.keys()):
        if expected[key] != actual[key]:
            yield _item(
                f"{baseline.qualified_name}.{key[1]}",
                DriftKind.BREAKING,
                Severity.HIGH,
                f"Approved {key[0]} constraint definition changed.",
                "Restore the definition or review integrity impact before updating the baseline.",
            )


def compare_schema_snapshots(baseline: SchemaSnapshot, current: SchemaSnapshot) -> DriftReport:
    expected_tables = {table.qualified_name: table for table in baseline.tables}
    actual_tables = {table.qualified_name: table for table in current.tables}
    items: list[DriftItem] = list(validate_governance(current))
    for name in sorted(expected_tables.keys() - actual_tables.keys()):
        items.append(
            _item(
                name,
                DriftKind.BREAKING,
                Severity.CRITICAL,
                "Approved table was removed.",
                "Restore the table or record and approve an explicit removal decision.",
            )
        )
    for name in sorted(actual_tables.keys() - expected_tables.keys()):
        items.append(
            _item(
                name,
                DriftKind.BREAKING,
                Severity.CRITICAL,
                "New table is not approved in the baseline.",
                "Classify every column and update the baseline through explicit review.",
            )
        )
    for name in sorted(expected_tables.keys() & actual_tables.keys()):
        items.extend(_compare_columns(expected_tables[name], actual_tables[name]))
        items.extend(_compare_constraints(expected_tables[name], actual_tables[name]))

    expected_relations = set(baseline.logical_relationships)
    actual_relations = set(current.logical_relationships)
    for relation in sorted(expected_relations ^ actual_relations):
        action = "removed" if relation in expected_relations else "added"
        items.append(
            _item(
                f"{relation.source}->{relation.target}",
                DriftKind.GOVERNANCE,
                Severity.HIGH,
                f"Approved logical relationship was {action}.",
                "Review relationship evidence and explicitly update the baseline.",
            )
        )
    return DriftReport(tuple(sorted(set(items))))
