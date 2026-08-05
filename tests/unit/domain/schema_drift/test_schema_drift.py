from __future__ import annotations

from dataclasses import replace

from src.domain.schema_drift import (
    ColumnSnapshot,
    ConsistencyGroupSnapshot,
    ConstraintSnapshot,
    DriftKind,
    LogicalRelationshipSnapshot,
    SchemaSnapshot,
    Severity,
    TableSnapshot,
    compare_schema_snapshots,
)


def _snapshot() -> SchemaSnapshot:
    return SchemaSnapshot(
        version=1,
        tables=(
            TableSnapshot(
                schema="crm",
                name="clienti",
                columns=(
                    ColumnSnapshot(
                        1, "cliente_id", "bigint", "int8", False, "PII-indiretta", "preserve_technical_key", None
                    ),
                    ColumnSnapshot(
                        2, "email", "character varying", "varchar", False, "PII-diretta", "mask_email", "customer_email"
                    ),
                ),
                constraints=(
                    ConstraintSnapshot("primary_key", "clienti_pkey", ("cliente_id",), "PRIMARY KEY (cliente_id)"),
                ),
            ),
        ),
        logical_relationships=(
            LogicalRelationshipSnapshot("billing.fatture.cliente_id", "crm.clienti.cliente_id", "logical_confirmed"),
        ),
        masking_rules=("mask_email", "preserve_technical_key"),
        consistency_groups=(ConsistencyGroupSnapshot("customer_email", ("crm.clienti.email",)),),
    )


def test_equal_snapshots_have_no_drift() -> None:
    report = compare_schema_snapshots(_snapshot(), _snapshot())
    assert report.has_drift is False
    assert report.items == ()


def test_breaking_structural_changes_are_reported_with_remediation() -> None:
    baseline = _snapshot()
    table = baseline.tables[0]
    changed_identifier = replace(table.columns[0], data_type="integer", udt_name="int4")
    current = replace(
        baseline,
        tables=(replace(table, columns=(changed_identifier,), constraints=()),),
        logical_relationships=(),
    )
    report = compare_schema_snapshots(baseline, current)
    messages = {item.message for item in report.items}
    assert "Approved column was removed." in messages
    assert "Approved primary_key constraint was removed." in messages
    assert any("Type changed" in message for message in messages)
    assert any(item.kind is DriftKind.GOVERNANCE for item in report.items)
    assert all(item.remediation for item in report.items)


def test_new_unclassified_table_and_column_are_critical_governance_findings() -> None:
    baseline = _snapshot()
    new_table = TableSnapshot(
        schema="crm",
        name="nuova_tabella",
        columns=(ColumnSnapshot(1, "valore", "text", "text", True, None, None, None),),
        constraints=(),
    )
    report = compare_schema_snapshots(baseline, replace(baseline, tables=(*baseline.tables, new_table)))
    assert any(item.path == "crm.nuova_tabella" and item.severity is Severity.CRITICAL for item in report.items)
    assert any(item.path == "crm.nuova_tabella.valore" and item.kind is DriftKind.GOVERNANCE for item in report.items)


def test_governance_changes_and_invalid_consistency_group_are_detected_deterministically() -> None:
    baseline = _snapshot()
    table = baseline.tables[0]
    changed_email = replace(table.columns[1], classification="Non-PII", consistency_group="missing")
    current = replace(baseline, tables=(replace(table, columns=(table.columns[0], changed_email)),))
    first = compare_schema_snapshots(baseline, current)
    second = compare_schema_snapshots(baseline, current)
    assert first == second
    assert [item.path for item in first.items] == sorted(item.path for item in first.items)
    assert first.count(DriftKind.GOVERNANCE) == 3
