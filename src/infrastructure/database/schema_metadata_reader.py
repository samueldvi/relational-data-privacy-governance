from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from psycopg import Connection

from src.domain.schema_drift import (
    ColumnSnapshot,
    ConsistencyGroupSnapshot,
    ConstraintSnapshot,
    LogicalRelationshipSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)
from src.infrastructure.config.loader import load_yaml_path

CONSTRAINT_KINDS = {"p": "primary_key", "f": "foreign_key", "u": "unique", "c": "check"}


class PostgresSchemaMetadataReader:
    def __init__(
        self,
        connect: Callable[[], Connection],
        schemas: tuple[str, ...],
        registry_path: Path,
        masking_rules_path: Path,
        consistency_groups_path: Path,
    ) -> None:
        self._connect = connect
        self._schemas = schemas
        self._registry_path = registry_path
        self._masking_rules_path = masking_rules_path
        self._consistency_groups_path = consistency_groups_path

    def snapshot(self) -> SchemaSnapshot:
        registry = load_yaml_path(self._registry_path)["columns"]
        registry_by_column = {
            f"{record['schema_name']}.{record['table_name']}.{record['column_name']}": record for record in registry
        }
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema, table_name, column_name, ordinal_position,
                       data_type, udt_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = ANY(%s)
                ORDER BY table_schema, table_name, ordinal_position
                """,
                (list(self._schemas),),
            )
            column_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT source_ns.nspname,
                       source_table.relname,
                       constraint_def.conname,
                       constraint_def.contype,
                       pg_get_constraintdef(constraint_def.oid, true),
                       ARRAY(
                           SELECT attribute_def.attname
                           FROM unnest(constraint_def.conkey) WITH ORDINALITY AS key(attnum, position)
                           JOIN pg_attribute AS attribute_def
                             ON attribute_def.attrelid = constraint_def.conrelid
                            AND attribute_def.attnum = key.attnum
                           ORDER BY key.position
                       ),
                       target_ns.nspname,
                       target_table.relname,
                       CASE WHEN constraint_def.contype = 'f' THEN ARRAY(
                           SELECT attribute_def.attname
                           FROM unnest(constraint_def.confkey) WITH ORDINALITY AS key(attnum, position)
                           JOIN pg_attribute AS attribute_def
                             ON attribute_def.attrelid = constraint_def.confrelid
                            AND attribute_def.attnum = key.attnum
                           ORDER BY key.position
                       ) ELSE ARRAY[]::name[] END
                FROM pg_constraint AS constraint_def
                JOIN pg_class AS source_table ON source_table.oid = constraint_def.conrelid
                JOIN pg_namespace AS source_ns ON source_ns.oid = source_table.relnamespace
                LEFT JOIN pg_class AS target_table ON target_table.oid = constraint_def.confrelid
                LEFT JOIN pg_namespace AS target_ns ON target_ns.oid = target_table.relnamespace
                WHERE source_ns.nspname = ANY(%s)
                  AND constraint_def.contype IN ('p', 'f', 'u', 'c')
                ORDER BY source_ns.nspname, source_table.relname,
                         constraint_def.contype, constraint_def.conname
                """,
                (list(self._schemas),),
            )
            constraint_rows = cursor.fetchall()

        columns_by_table: dict[tuple[str, str], list[ColumnSnapshot]] = defaultdict(list)
        for schema, table, column, position, data_type, udt_name, nullable in column_rows:
            qualified = f"{schema}.{table}.{column}"
            governance = registry_by_column.get(qualified, {})
            columns_by_table[(schema, table)].append(
                ColumnSnapshot(
                    ordinal_position=position,
                    name=column,
                    data_type=data_type,
                    udt_name=udt_name,
                    nullable=nullable == "YES",
                    classification=governance.get("pii_category"),
                    masking_rule=governance.get("masking_rule"),
                    consistency_group=governance.get("consistency_group"),
                )
            )

        constraints_by_table: dict[tuple[str, str], list[ConstraintSnapshot]] = defaultdict(list)
        for schema, table, name, kind, definition, columns, target_schema, target_table, targets in constraint_rows:
            constraints_by_table[(schema, table)].append(
                ConstraintSnapshot(
                    kind=CONSTRAINT_KINDS[kind],
                    name=name,
                    columns=tuple(columns),
                    definition=definition,
                    target_schema=target_schema,
                    target_table=target_table,
                    target_columns=tuple(targets),
                )
            )

        tables = tuple(
            TableSnapshot(
                schema=schema,
                name=table,
                columns=tuple(columns),
                constraints=tuple(constraints_by_table[(schema, table)]),
            )
            for (schema, table), columns in sorted(columns_by_table.items())
        )
        relationships = _confirmed_logical_relationships(registry)
        rules = load_yaml_path(self._masking_rules_path)["rules"]
        groups = load_yaml_path(self._consistency_groups_path)["groups"]
        return SchemaSnapshot(
            version=1,
            tables=tables,
            logical_relationships=relationships,
            masking_rules=tuple(sorted(rules)),
            consistency_groups=tuple(
                ConsistencyGroupSnapshot(name=name, columns=tuple(sorted(group["columns"])))
                for name, group in sorted(groups.items())
            ),
        )


def _confirmed_logical_relationships(registry: list[dict[str, Any]]) -> tuple[LogicalRelationshipSnapshot, ...]:
    relationships = {
        LogicalRelationshipSnapshot(
            source=f"{record['schema_name']}.{record['table_name']}.{record['column_name']}",
            target=str(relationship["target"]),
            status="logical_confirmed",
        )
        for record in registry
        for relationship in record.get("logical_relationship", [])
        if relationship.get("status") == "logical_confirmed"
    }
    return tuple(sorted(relationships))
