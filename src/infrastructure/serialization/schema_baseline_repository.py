from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.domain.schema_drift import (
    ColumnSnapshot,
    ConsistencyGroupSnapshot,
    ConstraintSnapshot,
    LogicalRelationshipSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)
from src.infrastructure.config.loader import load_yaml_path, write_yaml_path
from src.shared.errors import ConfigurationError


class SchemaBaselineRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> SchemaSnapshot:
        if not self.path.exists():
            raise ConfigurationError(f"Schema baseline is missing: {self.path}.")
        return _snapshot_from_document(load_yaml_path(self.path))

    def save(self, snapshot: SchemaSnapshot) -> None:
        write_yaml_path(self.path, _snapshot_to_document(snapshot), sort_keys=False)


def _snapshot_to_document(snapshot: SchemaSnapshot) -> dict[str, Any]:
    grouped_tables: dict[str, list[TableSnapshot]] = defaultdict(list)
    for table in snapshot.tables:
        grouped_tables[table.schema].append(table)
    schemas = []
    for schema_name in sorted(grouped_tables):
        tables = []
        for table in sorted(grouped_tables[schema_name], key=lambda item: item.name):
            tables.append(
                {
                    "name": table.name,
                    "columns": [
                        {
                            "name": column.name,
                            "ordinal_position": column.ordinal_position,
                            "data_type": column.data_type,
                            "udt_name": column.udt_name,
                            "nullable": column.nullable,
                            "classification": column.classification,
                            "masking_rule": column.masking_rule,
                            "consistency_group": column.consistency_group,
                        }
                        for column in table.columns
                    ],
                    "constraints": [
                        {
                            "name": constraint.name,
                            "kind": constraint.kind,
                            "columns": list(constraint.columns),
                            "definition": constraint.definition,
                            "target_schema": constraint.target_schema,
                            "target_table": constraint.target_table,
                            "target_columns": list(constraint.target_columns),
                        }
                        for constraint in table.constraints
                    ],
                }
            )
        schemas.append({"name": schema_name, "tables": tables})
    return {
        "version": snapshot.version,
        "schemas": schemas,
        "logical_relationships": [
            {"source": relation.source, "target": relation.target, "status": relation.status}
            for relation in snapshot.logical_relationships
        ],
        "masking_rules": list(snapshot.masking_rules),
        "consistency_groups": [
            {"name": group.name, "columns": list(group.columns)} for group in snapshot.consistency_groups
        ],
    }


def _snapshot_from_document(document: dict[str, Any]) -> SchemaSnapshot:
    try:
        tables = []
        for schema in document["schemas"]:
            for table in schema["tables"]:
                columns = tuple(
                    ColumnSnapshot(
                        ordinal_position=int(column["ordinal_position"]),
                        name=str(column["name"]),
                        data_type=str(column["data_type"]),
                        udt_name=str(column["udt_name"]),
                        nullable=bool(column["nullable"]),
                        classification=column.get("classification"),
                        masking_rule=column.get("masking_rule"),
                        consistency_group=column.get("consistency_group"),
                    )
                    for column in table["columns"]
                )
                constraints = tuple(
                    ConstraintSnapshot(
                        kind=str(constraint["kind"]),
                        name=str(constraint["name"]),
                        columns=tuple(str(value) for value in constraint["columns"]),
                        definition=str(constraint["definition"]),
                        target_schema=constraint.get("target_schema"),
                        target_table=constraint.get("target_table"),
                        target_columns=tuple(str(value) for value in constraint.get("target_columns", [])),
                    )
                    for constraint in table["constraints"]
                )
                tables.append(
                    TableSnapshot(
                        schema=str(schema["name"]),
                        name=str(table["name"]),
                        columns=columns,
                        constraints=constraints,
                    )
                )
        relationships = tuple(
            LogicalRelationshipSnapshot(
                source=str(relation["source"]),
                target=str(relation["target"]),
                status=str(relation["status"]),
            )
            for relation in document["logical_relationships"]
        )
        groups = tuple(
            ConsistencyGroupSnapshot(
                name=str(group["name"]),
                columns=tuple(str(value) for value in group["columns"]),
            )
            for group in document["consistency_groups"]
        )
        return SchemaSnapshot(
            version=int(document["version"]),
            tables=tuple(sorted(tables)),
            logical_relationships=tuple(sorted(relationships)),
            masking_rules=tuple(str(value) for value in document["masking_rules"]),
            consistency_groups=tuple(sorted(groups)),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(f"Schema baseline {document.get('version', 'unknown')} is invalid.") from error
