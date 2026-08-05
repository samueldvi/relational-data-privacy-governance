"""Technical PostgreSQL inventory and logical relationship analysis."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from psycopg import sql

from src.infrastructure.database.connection import get_connection

SOURCE_SCHEMAS = ("billing", "crm", "hr")
OUTPUT_DIRECTORY = Path("output")
INVENTORY_PATH = OUTPUT_DIRECTORY / "inventory.csv"
RELATIONSHIPS_PATH = OUTPUT_DIRECTORY / "logical_relationships.csv"

INVENTORY_FIELDS = (
    "schema_name",
    "table_name",
    "column_name",
    "ordinal_position",
    "data_type",
    "udt_name",
    "character_maximum_length",
    "numeric_precision",
    "numeric_scale",
    "is_nullable",
    "column_default",
    "is_primary_key",
    "is_unique",
    "is_foreign_key",
    "constraint_name",
    "referenced_schema",
    "referenced_table",
    "referenced_column",
    "check_constraint",
    "table_row_count",
)

RELATIONSHIP_FIELDS = (
    "source_schema",
    "source_table",
    "source_column",
    "target_schema",
    "target_table",
    "target_column",
    "relationship_status",
    "type_compatible",
    "source_non_null_count",
    "source_distinct_count",
    "matched_distinct_count",
    "match_percentage",
    "orphan_count",
    "target_is_unique",
    "name_similarity",
    "cardinality",
    "cross_schema",
    "evidence",
    "review_note",
)

CONFIRMED_LOGICAL_RELATIONSHIPS = {
    ("hr", "reparti", "responsabile_id", "hr", "dipendenti", "dipendente_id"),
    ("billing", "fatture", "cliente_id", "crm", "clienti", "cliente_id"),
}

INTEGER_TYPES = {"int2", "int4", "int8"}


@dataclass(frozen=True)
class ColumnKey:
    schema: str
    table: str
    column: str


@dataclass(frozen=True)
class RelationshipKey:
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str

    def as_tuple(self) -> tuple[str, ...]:
        return (
            self.source_schema,
            self.source_table,
            self.source_column,
            self.target_schema,
            self.target_table,
            self.target_column,
        )


def _qualified_identifier(schema: str, table: str) -> sql.Composed:
    return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))


def _fetch_columns(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT table_schema, table_name, column_name, ordinal_position, data_type,
               udt_name, character_maximum_length, numeric_precision, numeric_scale,
               is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = ANY(%s)
        ORDER BY table_schema, table_name, ordinal_position
        """,
        (list(SOURCE_SCHEMAS),),
    )
    fields = (
        "schema_name",
        "table_name",
        "column_name",
        "ordinal_position",
        "data_type",
        "udt_name",
        "character_maximum_length",
        "numeric_precision",
        "numeric_scale",
        "is_nullable",
        "column_default",
    )
    return [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]


def _fetch_table_counts(cursor: Any, tables: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    statements = []
    for schema, table in tables:
        statements.append(
            sql.SQL("SELECT {} AS schema_name, {} AS table_name, count(*) AS row_count FROM {}").format(
                sql.Literal(schema), sql.Literal(table), _qualified_identifier(schema, table)
            )
        )
    cursor.execute(sql.SQL(" UNION ALL ").join(statements))
    return {(schema, table): count for schema, table, count in cursor.fetchall()}


def _fetch_constraint_members(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT source_ns.nspname AS schema_name,
               source_table.relname AS table_name,
               source_att.attname AS column_name,
               constraint_def.conname AS constraint_name,
               constraint_def.contype AS constraint_type,
               target_ns.nspname AS referenced_schema,
               target_table.relname AS referenced_table,
               target_att.attname AS referenced_column,
               CASE WHEN constraint_def.contype = 'c'
                    THEN pg_get_constraintdef(constraint_def.oid, true)
                    ELSE NULL END AS check_constraint
        FROM pg_constraint AS constraint_def
        JOIN pg_class AS source_table ON source_table.oid = constraint_def.conrelid
        JOIN pg_namespace AS source_ns ON source_ns.oid = source_table.relnamespace
        CROSS JOIN LATERAL unnest(constraint_def.conkey)
            WITH ORDINALITY AS source_key(attnum, key_position)
        JOIN pg_attribute AS source_att
          ON source_att.attrelid = source_table.oid
         AND source_att.attnum = source_key.attnum
        LEFT JOIN pg_class AS target_table ON target_table.oid = constraint_def.confrelid
        LEFT JOIN pg_namespace AS target_ns ON target_ns.oid = target_table.relnamespace
        LEFT JOIN pg_attribute AS target_att
          ON target_att.attrelid = target_table.oid
         AND target_att.attnum = constraint_def.confkey[source_key.key_position]
        WHERE source_ns.nspname = ANY(%s)
          AND constraint_def.contype IN ('p', 'u', 'f', 'c')
        ORDER BY source_ns.nspname, source_table.relname, source_att.attnum,
                 constraint_def.contype, constraint_def.conname
        """,
        (list(SOURCE_SCHEMAS),),
    )
    fields = (
        "schema_name",
        "table_name",
        "column_name",
        "constraint_name",
        "constraint_type",
        "referenced_schema",
        "referenced_table",
        "referenced_column",
        "check_constraint",
    )
    return [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]


def collect_inventory(connection: Any) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        columns = _fetch_columns(cursor)
        tables = sorted({(row["schema_name"], row["table_name"]) for row in columns})
        table_counts = _fetch_table_counts(cursor, tables)
        constraint_members = _fetch_constraint_members(cursor)

    constraints: dict[ColumnKey, list[dict[str, Any]]] = defaultdict(list)
    for member in constraint_members:
        key = ColumnKey(member["schema_name"], member["table_name"], member["column_name"])
        constraints[key].append(member)

    inventory = []
    for column in columns:
        key = ColumnKey(column["schema_name"], column["table_name"], column["column_name"])
        members = constraints[key]

        def joined(
            field: str,
            *,
            constraint_type: str | None = None,
            constraint_members: tuple[dict[str, Any], ...] = tuple(members),
        ) -> str:
            values = {
                str(member[field])
                for member in constraint_members
                if member[field] is not None
                and (constraint_type is None or member["constraint_type"] == constraint_type)
            }
            return "|".join(sorted(values))

        types = {member["constraint_type"] for member in members}
        row = dict(column)
        row.update(
            {
                "is_primary_key": "true" if "p" in types else "false",
                "is_unique": "true" if "u" in types else "false",
                "is_foreign_key": "true" if "f" in types else "false",
                "constraint_name": joined("constraint_name"),
                "referenced_schema": joined("referenced_schema", constraint_type="f"),
                "referenced_table": joined("referenced_table", constraint_type="f"),
                "referenced_column": joined("referenced_column", constraint_type="f"),
                "check_constraint": joined("check_constraint", constraint_type="c"),
                "table_row_count": table_counts[(column["schema_name"], column["table_name"])],
            }
        )
        inventory.append(row)
    return inventory


def _type_compatible(source_type: str, target_type: str) -> bool:
    return source_type == target_type or {source_type, target_type} <= INTEGER_TYPES


def _name_similarity(source_column: str, target_column: str) -> float:
    return round(SequenceMatcher(None, source_column.lower(), target_column.lower()).ratio(), 4)


def _fetch_declared_relationships(cursor: Any) -> list[RelationshipKey]:
    cursor.execute(
        """
        SELECT source_ns.nspname, source_table.relname, source_att.attname,
               target_ns.nspname, target_table.relname, target_att.attname
        FROM pg_constraint AS constraint_def
        JOIN pg_class AS source_table ON source_table.oid = constraint_def.conrelid
        JOIN pg_namespace AS source_ns ON source_ns.oid = source_table.relnamespace
        JOIN pg_class AS target_table ON target_table.oid = constraint_def.confrelid
        JOIN pg_namespace AS target_ns ON target_ns.oid = target_table.relnamespace
        CROSS JOIN LATERAL unnest(constraint_def.conkey)
            WITH ORDINALITY AS source_key(attnum, key_position)
        JOIN pg_attribute AS source_att
          ON source_att.attrelid = source_table.oid AND source_att.attnum = source_key.attnum
        JOIN pg_attribute AS target_att
          ON target_att.attrelid = target_table.oid
         AND target_att.attnum = constraint_def.confkey[source_key.key_position]
        WHERE constraint_def.contype = 'f' AND source_ns.nspname = ANY(%s)
        ORDER BY 1, 2, 3, 4, 5, 6
        """,
        (list(SOURCE_SCHEMAS),),
    )
    return [RelationshipKey(*row) for row in cursor.fetchall()]


def _fetch_single_column_unique_keys(cursor: Any) -> set[ColumnKey]:
    cursor.execute(
        """
        SELECT schema_def.nspname, table_def.relname, attribute_def.attname
        FROM pg_constraint AS constraint_def
        JOIN pg_class AS table_def ON table_def.oid = constraint_def.conrelid
        JOIN pg_namespace AS schema_def ON schema_def.oid = table_def.relnamespace
        JOIN pg_attribute AS attribute_def
          ON attribute_def.attrelid = table_def.oid
         AND attribute_def.attnum = constraint_def.conkey[1]
        WHERE schema_def.nspname = ANY(%s)
          AND constraint_def.contype IN ('p', 'u')
          AND cardinality(constraint_def.conkey) = 1
        """,
        (list(SOURCE_SCHEMAS),),
    )
    return {ColumnKey(*row) for row in cursor.fetchall()}


def _relationship_metrics(cursor: Any, relationship: RelationshipKey) -> dict[str, Any]:
    source = _qualified_identifier(relationship.source_schema, relationship.source_table)
    target = _qualified_identifier(relationship.target_schema, relationship.target_table)
    source_column = sql.Identifier(relationship.source_column)
    target_column = sql.Identifier(relationship.target_column)
    cursor.execute(
        sql.SQL(
            """
            SELECT count(s.{source_column}) AS source_non_null_count,
                   count(DISTINCT s.{source_column}) AS source_distinct_count,
                   count(DISTINCT s.{source_column}) FILTER (WHERE t.{target_column} IS NOT NULL)
                       AS matched_distinct_count,
                   count(*) FILTER (
                       WHERE s.{source_column} IS NOT NULL AND t.{target_column} IS NULL
                   ) AS orphan_count
            FROM {source} AS s
            LEFT JOIN {target} AS t ON t.{target_column} = s.{source_column}
            """
        ).format(
            source_column=source_column,
            target_column=target_column,
            source=source,
            target=target,
        )
    )
    source_non_null, source_distinct, matched_distinct, orphan_count = cursor.fetchone()
    percentage = 100.0 if source_distinct == 0 else matched_distinct * 100.0 / source_distinct
    return {
        "source_non_null_count": source_non_null,
        "source_distinct_count": source_distinct,
        "matched_distinct_count": matched_distinct,
        "match_percentage": f"{percentage:.2f}",
        "orphan_count": orphan_count,
        "cardinality": "one-to-one" if source_non_null == source_distinct else "many-to-one",
    }


def collect_relationships(connection: Any, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    column_lookup = {ColumnKey(row["schema_name"], row["table_name"], row["column_name"]): row for row in inventory}
    with connection.cursor() as cursor:
        declared = _fetch_declared_relationships(cursor)
        single_column_unique_keys = _fetch_single_column_unique_keys(cursor)
        target_columns = [(key, row) for key, row in column_lookup.items() if key in single_column_unique_keys]
        declared_set = {relationship.as_tuple() for relationship in declared}
        candidates = set(declared)
        candidates.update(RelationshipKey(*values) for values in CONFIRMED_LOGICAL_RELATIONSHIPS)

        for source_key, source_row in column_lookup.items():
            if not source_key.column.endswith("_id"):
                continue
            for target_key, target_row in target_columns:
                candidate = RelationshipKey(
                    source_key.schema,
                    source_key.table,
                    source_key.column,
                    target_key.schema,
                    target_key.table,
                    target_key.column,
                )
                if source_key == target_key or candidate.as_tuple() in declared_set:
                    continue
                if source_key.column != target_key.column:
                    continue
                if _type_compatible(source_row["udt_name"], target_row["udt_name"]):
                    candidates.add(candidate)

        relationships = []
        for relationship in sorted(candidates, key=RelationshipKey.as_tuple):
            source_row = column_lookup[
                ColumnKey(relationship.source_schema, relationship.source_table, relationship.source_column)
            ]
            target_row = column_lookup[
                ColumnKey(relationship.target_schema, relationship.target_table, relationship.target_column)
            ]
            compatible = _type_compatible(source_row["udt_name"], target_row["udt_name"])
            target_key = ColumnKey(relationship.target_schema, relationship.target_table, relationship.target_column)
            target_unique = target_key in single_column_unique_keys
            metrics = _relationship_metrics(cursor, relationship)
            confirmed = relationship.as_tuple() in CONFIRMED_LOGICAL_RELATIONSHIPS

            if relationship.as_tuple() in declared_set:
                status = "declared"
                review_note = "Foreign key dichiarata nel catalogo PostgreSQL."
            elif (
                confirmed
                and compatible
                and target_unique
                and metrics["orphan_count"] == 0
                and metrics["match_percentage"] == "100.00"
            ):
                status = "logical_confirmed"
                review_note = "Relazione logica approvata nel decision log; non creare una FK."
            elif compatible and target_unique:
                status = "logical_suspected"
                review_note = "Evidenza tecnica presente; richiede validazione applicativa esplicita."
            else:
                status = "not_confirmed"
                review_note = "Evidenza insufficiente per proporre una relazione."

            evidence = (
                f"types={'compatible' if compatible else 'incompatible'}; "
                f"target_unique={str(target_unique).lower()}; "
                f"matched={metrics['matched_distinct_count']}/{metrics['source_distinct_count']}; "
                f"orphans={metrics['orphan_count']}"
            )
            row = {
                "source_schema": relationship.source_schema,
                "source_table": relationship.source_table,
                "source_column": relationship.source_column,
                "target_schema": relationship.target_schema,
                "target_table": relationship.target_table,
                "target_column": relationship.target_column,
                "relationship_status": status,
                "type_compatible": str(compatible).lower(),
                **metrics,
                "target_is_unique": str(target_unique).lower(),
                "name_similarity": f"{_name_similarity(relationship.source_column, relationship.target_column):.4f}",
                "cross_schema": str(relationship.source_schema != relationship.target_schema).lower(),
                "evidence": evidence,
                "review_note": review_note,
            }
            relationships.append(row)
    return relationships


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_inventory(output_directory: Path = OUTPUT_DIRECTORY) -> dict[str, Any]:
    with get_connection() as connection:
        inventory = collect_inventory(connection)
        relationships = collect_relationships(connection, inventory)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT contype, count(*)
                FROM pg_constraint AS constraint_def
                JOIN pg_class AS table_def ON table_def.oid = constraint_def.conrelid
                JOIN pg_namespace AS schema_def ON schema_def.oid = table_def.relnamespace
                WHERE schema_def.nspname = ANY(%s)
                  AND contype IN ('p', 'f', 'u', 'c')
                GROUP BY contype
                """,
                (list(SOURCE_SCHEMAS),),
            )
            constraint_counts: dict[str, int] = dict(cursor.fetchall())

    inventory_path = output_directory / "inventory.csv"
    relationships_path = output_directory / "logical_relationships.csv"
    _write_csv(inventory_path, INVENTORY_FIELDS, inventory)
    _write_csv(relationships_path, RELATIONSHIP_FIELDS, relationships)
    return {
        "schemas": len({row["schema_name"] for row in inventory}),
        "tables": len({(row["schema_name"], row["table_name"]) for row in inventory}),
        "columns": len(inventory),
        "primary_keys": constraint_counts.get("p", 0),
        "foreign_keys": constraint_counts.get("f", 0),
        "unique_constraints": constraint_counts.get("u", 0),
        "check_constraints": constraint_counts.get("c", 0),
        "declared_relationships": sum(row["relationship_status"] == "declared" for row in relationships),
        "confirmed_logical_relationships": sum(
            row["relationship_status"] == "logical_confirmed" for row in relationships
        ),
        "inventory_path": inventory_path,
        "relationships_path": relationships_path,
    }


def main() -> None:
    summary = generate_inventory()
    print(
        "Inventory generated: "
        f"{summary['schemas']} schemas, {summary['tables']} tables, {summary['columns']} columns; "
        f"PK={summary['primary_keys']}, FK={summary['foreign_keys']}, "
        f"UNIQUE={summary['unique_constraints']}, CHECK={summary['check_constraints']}."
    )
    print(
        f"Relationships: {summary['declared_relationships']} declared, "
        f"{summary['confirmed_logical_relationships']} logical_confirmed."
    )
    print(f"Written: {summary['inventory_path']}, {summary['relationships_path']}")


if __name__ == "__main__":
    main()
