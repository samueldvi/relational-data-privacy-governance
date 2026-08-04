"""Transactional creation, population and validation of masked schemas."""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

import yaml
from psycopg import sql

from src.db import get_connection
from src.masking import (
    CONSISTENCY_GROUPS_PATH,
    REGISTRY_PATH,
    InvalidConfigurationError,
    ReviewRequiredError,
    get_masking_secret,
    mask_email,
    mask_iban,
    mask_person_name,
    mask_phone,
    mask_postal_address,
    mask_tax_code,
    normalize_email,
    normalize_iban,
    normalize_name,
    normalize_phone,
    normalize_tax_code,
    preserve_technical_key,
    preserve_value,
    redact_free_text,
    resolve_collisions,
    shift_birth_date,
    validate_masking_configuration,
)
from src.masking_manifest import (
    MANIFEST_PATH,
    current_git_commit,
    finalize_manifest,
    table_checksum,
    write_manifest,
)


EXECUTION_CONFIG_PATH = Path("config/masking_execution.yml")
SOURCE_SCHEMAS = ("billing", "crm", "hr")
SCHEMA_MAPPING = {
    "crm": "masked_crm", "hr": "masked_hr", "billing": "masked_billing",
}
MASKED_SCHEMAS = tuple(SCHEMA_MAPPING.values())
SUPPORTED_AMBIGUOUS_STRATEGIES = {
    "block", "redact_detected_patterns", "preserve_with_approved_exception",
}
PARTIAL_CARD_PATTERN = re.compile(
    r"(?<!\w)(?:\d[ -]?){4}(?:[*Xx][*Xx -]{2,})(?:\d[ -]?){4}(?!\w)"
)
RECOGNIZABLE_BANK_REFERENCE_PATTERN = re.compile(
    r"\b(?:SYNREF|CRO|TRN|BANKREF)[A-Z0-9-]{4,}\b", re.IGNORECASE
)


class MaskingPipelineError(Exception):
    """Base error for safe, aggregate-only pipeline failures."""


class PreconditionError(MaskingPipelineError):
    """Raised when a required registry, config or database state is invalid."""


class DependencyCycleError(MaskingPipelineError):
    """Raised when declared foreign keys contain an unsupported cycle."""


class MaskedValidationError(MaskingPipelineError):
    """Raised when a post-load validation fails."""


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as input_file:
        return yaml.safe_load(input_file)


def _qualified(schema_name: str, table_name: str) -> sql.Composed:
    return sql.SQL("{}.{}").format(sql.Identifier(schema_name), sql.Identifier(table_name))


def _source_table_name(masked_or_source: str) -> str:
    schema_name, table_name = masked_or_source.split(".")
    reverse = {masked: source for source, masked in SCHEMA_MAPPING.items()}
    return f"{reverse.get(schema_name, schema_name)}.{table_name}"


def _fetch_source_tables(cursor: Any) -> list[str]:
    cursor.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE' AND table_schema = ANY(%s)
        ORDER BY table_schema, table_name
        """,
        (list(SOURCE_SCHEMAS),),
    )
    return [f"{schema_name}.{table_name}" for schema_name, table_name in cursor.fetchall()]


def _fetch_declared_foreign_keys(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT source_ns.nspname, source_table.relname, constraint_def.conname,
               target_ns.nspname, target_table.relname,
               pg_get_constraintdef(constraint_def.oid, true),
               ARRAY(
                   SELECT source_att.attname FROM unnest(constraint_def.conkey)
                   WITH ORDINALITY AS source_key(attnum, position)
                   JOIN pg_attribute AS source_att
                     ON source_att.attrelid=source_table.oid AND source_att.attnum=source_key.attnum
                   ORDER BY source_key.position
               ),
               ARRAY(
                   SELECT target_att.attname FROM unnest(constraint_def.confkey)
                   WITH ORDINALITY AS target_key(attnum, position)
                   JOIN pg_attribute AS target_att
                     ON target_att.attrelid=target_table.oid AND target_att.attnum=target_key.attnum
                   ORDER BY target_key.position
               )
        FROM pg_constraint AS constraint_def
        JOIN pg_class AS source_table ON source_table.oid = constraint_def.conrelid
        JOIN pg_namespace AS source_ns ON source_ns.oid = source_table.relnamespace
        JOIN pg_class AS target_table ON target_table.oid = constraint_def.confrelid
        JOIN pg_namespace AS target_ns ON target_ns.oid = target_table.relnamespace
        WHERE constraint_def.contype = 'f' AND source_ns.nspname = ANY(%s)
        ORDER BY source_ns.nspname, source_table.relname, constraint_def.conname
        """,
        (list(SOURCE_SCHEMAS),),
    )
    fields = (
        "source_schema", "source_table", "constraint_name", "target_schema",
        "target_table", "definition", "source_columns", "target_columns",
    )
    return [dict(zip(fields, row)) for row in cursor.fetchall()]


def calculate_load_order(tables: list[str], foreign_keys: list[dict[str, Any]]) -> list[str]:
    dependencies = {table: set() for table in tables}
    for foreign_key in foreign_keys:
        child = f"{foreign_key['source_schema']}.{foreign_key['source_table']}"
        parent = f"{foreign_key['target_schema']}.{foreign_key['target_table']}"
        if child != parent:
            dependencies[child].add(parent)
    order: list[str] = []
    remaining = {table: set(parents) for table, parents in dependencies.items()}
    while remaining:
        ready = sorted(table for table, parents in remaining.items() if not parents)
        if not ready:
            raise DependencyCycleError("Declared foreign keys contain a dependency cycle that cannot be loaded safely.")
        order.extend(ready)
        for table in ready:
            remaining.pop(table)
        for parents in remaining.values():
            parents.difference_update(ready)
    return order


def _validate_execution_decision(
    execution: dict[str, Any], registry_by_column: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if execution.get("default_ambiguous_strategy") != "block":
        raise PreconditionError("The default ambiguous-column strategy must remain block.")
    column = "billing.pagamenti.riferimento_bancario"
    record = registry_by_column.get(column)
    if not record or record["pii_category"] != "Dubbio" or record["masking_rule"] != "review_before_masking":
        raise PreconditionError("The controlled bank-reference column must remain Dubbio with review_before_masking.")
    decision = execution.get("ambiguous_columns", {}).get(column, {
        "strategy": execution["default_ambiguous_strategy"]
    })
    strategy = decision.get("strategy")
    if strategy not in SUPPORTED_AMBIGUOUS_STRATEGIES:
        raise PreconditionError("Unsupported ambiguous-column strategy.")
    if strategy == "block":
        raise ReviewRequiredError(
            "Masked loading is blocked pending an explicit versioned decision for billing.pagamenti.riferimento_bancario."
        )
    if strategy == "preserve_with_approved_exception" and not all(
        decision.get(field) for field in ("rationale", "source", "review_status")
    ):
        raise PreconditionError("A preserve exception requires rationale, source and confirmed review status.")
    if strategy != "block" and decision.get("review_status") != "confirmed":
        raise PreconditionError("The ambiguous-column decision must have review_status confirmed.")
    if strategy == "redact_detected_patterns" and not decision.get("residual_risk"):
        raise PreconditionError("Pattern redaction requires an explicit residual-risk statement.")
    return decision


def _registry() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    records = _load_yaml(REGISTRY_PATH)["columns"]
    indexed = {
        f"{record['schema_name']}.{record['table_name']}.{record['column_name']}": record
        for record in records
    }
    return records, indexed


def validate_preconditions(cursor: Any) -> dict[str, Any]:
    masking_summary = validate_masking_configuration()
    if masking_summary["registry_columns"] != 109:
        raise PreconditionError("Privacy Metadata Registry must contain exactly 109 columns.")
    secret = get_masking_secret()
    records, registry_by_column = _registry()
    if any(not record.get("pii_category") or not record.get("masking_rule") for record in records):
        raise PreconditionError("Every registry column must have a category and masking rule.")
    source_tables = _fetch_source_tables(cursor)
    if len(source_tables) != 20:
        raise PreconditionError("Exactly 20 source tables are required.")
    registry_tables = sorted({f"{record['schema_name']}.{record['table_name']}" for record in records})
    if source_tables != registry_tables:
        raise PreconditionError("Every source table must have a complete registry destination mapping.")
    execution = _load_yaml(EXECUTION_CONFIG_PATH)
    decision = _validate_execution_decision(execution, registry_by_column)
    reference_date = date.fromisoformat(str(execution["reference_date"]))
    foreign_keys = _fetch_declared_foreign_keys(cursor)
    load_order = calculate_load_order(source_tables, foreign_keys)
    return {
        "secret": secret, "records": records, "registry_by_column": registry_by_column,
        "source_tables": source_tables, "foreign_keys": foreign_keys,
        "load_order": load_order, "execution": execution, "decision": decision,
        "reference_date": reference_date, "masking_summary": masking_summary,
    }


def _primary_key_columns(cursor: Any, schema_name: str, table_name: str) -> list[str]:
    cursor.execute(
        """
        SELECT attribute_def.attname
        FROM pg_constraint AS constraint_def
        CROSS JOIN LATERAL unnest(constraint_def.conkey) WITH ORDINALITY AS key_def(attnum, position)
        JOIN pg_class AS table_def ON table_def.oid = constraint_def.conrelid
        JOIN pg_namespace AS schema_def ON schema_def.oid = table_def.relnamespace
        JOIN pg_attribute AS attribute_def
          ON attribute_def.attrelid = table_def.oid AND attribute_def.attnum = key_def.attnum
        WHERE constraint_def.contype = 'p' AND schema_def.nspname = %s AND table_def.relname = %s
        ORDER BY key_def.position
        """,
        (schema_name, table_name),
    )
    return [row[0] for row in cursor.fetchall()]


def _fetch_column_names(cursor: Any, schema_name: str, table_name: str) -> list[str]:
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position
        """,
        (schema_name, table_name),
    )
    return [row[0] for row in cursor.fetchall()]


def _fetch_all_source_data(
    cursor: Any, tables: list[str]
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[tuple[Any, ...]]]]:
    columns_by_table: dict[str, list[str]] = {}
    primary_keys: dict[str, list[str]] = {}
    data: dict[str, list[tuple[Any, ...]]] = {}
    for table in tables:
        schema_name, table_name = table.split(".")
        columns = _fetch_column_names(cursor, schema_name, table_name)
        keys = _primary_key_columns(cursor, schema_name, table_name)
        if not keys:
            raise PreconditionError("Every source table requires a primary key for deterministic ordering.")
        query = sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            _qualified(schema_name, table_name),
            sql.SQL(", ").join(map(sql.Identifier, keys)),
        )
        cursor.execute(query)
        columns_by_table[table] = columns
        primary_keys[table] = keys
        data[table] = cursor.fetchall()
    return columns_by_table, primary_keys, data


def _masker_for_domain(
    domain: str, *, secret: str, namespace: str
) -> tuple[Callable[[str], str], Callable[[str, int], str]]:
    if domain == "email_address":
        return normalize_email, lambda value, counter: mask_email(
            value, secret=secret, namespace=namespace, counter=counter
        ) or ""
    if domain == "italian_tax_code":
        return normalize_tax_code, lambda value, counter: mask_tax_code(
            value, secret=secret, namespace=namespace, counter=counter
        ) or ""
    if domain == "italian_iban":
        return normalize_iban, lambda value, counter: mask_iban(
            value, secret=secret, namespace=namespace, counter=counter
        ) or ""
    if domain == "phone_number":
        return normalize_phone, lambda value, counter: mask_phone(
            value, secret=secret, namespace=namespace, counter=counter
        ) or ""
    if domain == "person_name":
        return normalize_name, lambda value, counter: mask_person_name(
            value, secret=secret, namespace=namespace, counter=counter
        ) or ""
    if domain == "postal_address":
        return normalize_name, lambda value, counter: mask_postal_address(
            value, secret=secret, namespace=namespace, counter=counter
        ) or ""
    raise InvalidConfigurationError("No batch masking primitive exists for the requested domain.")


def _column_values(
    column: str, columns_by_table: dict[str, list[str]], data: dict[str, list[tuple[Any, ...]]]
) -> list[str]:
    schema_name, table_name, column_name = column.split(".")
    table = f"{schema_name}.{table_name}"
    index = columns_by_table[table].index(column_name)
    return [str(row[index]) for row in data[table] if row[index] not in (None, "")]


def _prepare_batch_mappings(
    context: dict[str, Any], columns_by_table: dict[str, list[str]],
    source_data: dict[str, list[tuple[Any, ...]]],
) -> tuple[dict[str, dict[str, str]], dict[tuple[str, str], dict[str, str]], dict[str, Any]]:
    groups = _load_yaml(CONSISTENCY_GROUPS_PATH)["groups"]
    secret = context["secret"]
    mappings: dict[str, dict[str, str]] = {}
    collision_details: dict[str, Any] = {}
    for group_name, group in groups.items():
        values = [
            value for column in group["columns"]
            for value in _column_values(column, columns_by_table, source_data)
        ]
        normalizer, generator = _masker_for_domain(
            group["data_domain"], secret=secret, namespace=group["namespace"]
        )
        resolution = resolve_collisions(
            values, normalizer=normalizer, candidate_generator=generator
        )
        mappings[group_name] = resolution.mapping
        collision_details[group_name] = {
            "values_processed": resolution.statistics.values_processed,
            "collisions_detected": resolution.statistics.collisions_detected,
            "collisions_resolved": resolution.statistics.collisions_resolved,
            "maximum_attempts": resolution.statistics.maximum_attempts,
        }

    contextual: dict[tuple[str, str], dict[str, str]] = {}
    for rule, domain in (("mask_person_name", "person_name"), ("mask_postal_address", "postal_address")):
        subjects = sorted({
            record["data_subject"] for record in context["records"]
            if record["masking_rule"] == rule
        })
        for subject in subjects:
            columns = [
                f"{record['schema_name']}.{record['table_name']}.{record['column_name']}"
                for record in context["records"]
                if record["masking_rule"] == rule and record["data_subject"] == subject
            ]
            values = [
                value for column in columns
                for value in _column_values(column, columns_by_table, source_data)
            ]
            namespace = f"{domain}.{subject}.v1"
            normalizer, generator = _masker_for_domain(
                domain, secret=secret, namespace=namespace
            )
            resolution = resolve_collisions(
                values, normalizer=normalizer, candidate_generator=generator
            )
            contextual[(rule, subject)] = resolution.mapping
            collision_details[f"{rule}:{subject}"] = {
                "values_processed": resolution.statistics.values_processed,
                "collisions_detected": resolution.statistics.collisions_detected,
                "collisions_resolved": resolution.statistics.collisions_resolved,
                "maximum_attempts": resolution.statistics.maximum_attempts,
            }
    return mappings, contextual, collision_details


def _known_names(
    records: list[dict[str, Any]], columns_by_table: dict[str, list[str]],
    source_data: dict[str, list[tuple[Any, ...]]],
) -> list[str]:
    names = set()
    for record in records:
        if record["data_domain"] != "person_name":
            continue
        column = f"{record['schema_name']}.{record['table_name']}.{record['column_name']}"
        names.update(_column_values(column, columns_by_table, source_data))
    return sorted(names, key=lambda value: (-len(value), value.casefold()))


def redact_bank_reference(value: str | None) -> str | None:
    redacted = redact_free_text(value)
    if redacted is None:
        return None
    redacted = PARTIAL_CARD_PATTERN.sub("[REDACTED_BANK_REFERENCE]", redacted)
    return RECOGNIZABLE_BANK_REFERENCE_PATTERN.sub(
        "[REDACTED_BANK_REFERENCE]", redacted
    )


def _transform_data(
    context: dict[str, Any], columns_by_table: dict[str, list[str]],
    source_data: dict[str, list[tuple[Any, ...]]],
) -> tuple[dict[str, list[tuple[Any, ...]]], dict[str, Any]]:
    group_mappings, contextual_mappings, collision_details = _prepare_batch_mappings(
        context, columns_by_table, source_data
    )
    approved_keys = {
        key for key, record in context["registry_by_column"].items()
        if record["masking_rule"] == "preserve_technical_key"
    }
    names = _known_names(context["records"], columns_by_table, source_data)
    transformed: dict[str, list[tuple[Any, ...]]] = {}
    rule_counts: Counter[str] = Counter()
    transformed_columns: set[str] = set()
    preserved_columns: set[str] = set()

    for table in context["load_order"]:
        columns = columns_by_table[table]
        output_rows = []
        for source_row in source_data[table]:
            row_context = dict(zip(columns, source_row))
            output_row = []
            for column_name, value in zip(columns, source_row):
                key = f"{table}.{column_name}"
                record = context["registry_by_column"][key]
                rule = record["masking_rule"]
                rule_counts[rule] += 1
                if rule == "preserve_technical_key":
                    masked_value = preserve_technical_key(
                        value, column=key, approved_columns=approved_keys
                    )
                    preserved_columns.add(key)
                elif rule == "preserve_value":
                    masked_value = preserve_value(value)
                    preserved_columns.add(key)
                elif rule == "review_before_masking":
                    strategy = context["decision"]["strategy"]
                    if strategy == "redact_detected_patterns":
                        masked_value = redact_bank_reference(value)
                    elif strategy == "preserve_with_approved_exception":
                        masked_value = preserve_value(value)
                    else:
                        raise ReviewRequiredError("Ambiguous bank reference remains blocked.")
                    transformed_columns.add(key)
                elif rule == "redact_free_text":
                    masked_value = redact_free_text(value, known_names=names)
                    transformed_columns.add(key)
                elif rule == "shift_birth_date":
                    masked_value = shift_birth_date(
                        value, secret=context["secret"], namespace=f"birth_date.{record['data_subject']}.v1",
                        reference_date=context["reference_date"],
                    )
                    transformed_columns.add(key)
                elif rule == "mask_contact_value":
                    contact_type = str(row_context["tipo"]).strip().lower()
                    if value in (None, ""):
                        masked_value = value
                    elif contact_type in {"email", "pec"}:
                        normalizer, generator = _masker_for_domain(
                            "email_address", secret=context["secret"],
                            namespace="contact_value.customer.email.v1",
                        )
                        masked_value = generator(str(value), 0)
                    elif contact_type == "telefono":
                        normalizer, generator = _masker_for_domain(
                            "phone_number", secret=context["secret"],
                            namespace="contact_value.customer.phone.v1",
                        )
                        masked_value = generator(str(value), 0)
                    else:
                        raise InvalidConfigurationError("Unsupported contact type during masked loading.")
                    transformed_columns.add(key)
                elif record["consistency_group"]:
                    group = record["consistency_group"]
                    group_config = _load_yaml(CONSISTENCY_GROUPS_PATH)["groups"][group]
                    normalizer, _ = _masker_for_domain(
                        group_config["data_domain"], secret=context["secret"],
                        namespace=group_config["namespace"],
                    )
                    masked_value = value if value in (None, "") else group_mappings[group][normalizer(str(value))]
                    transformed_columns.add(key)
                elif rule in {"mask_person_name", "mask_postal_address"}:
                    normalizer = normalize_name
                    masked_value = value if value in (None, "") else contextual_mappings[(rule, record["data_subject"])][normalizer(str(value))]
                    transformed_columns.add(key)
                else:
                    raise InvalidConfigurationError("Registry contains a masking rule unsupported by the loader.")
                output_row.append(masked_value)
            output_rows.append(tuple(output_row))
        transformed[table] = output_rows
    return transformed, {
        "collision_details": collision_details,
        "rule_counts": dict(sorted(rule_counts.items())),
        "transformed_columns": sorted(transformed_columns),
        "preserved_columns": sorted(preserved_columns),
        "known_names": names,
    }


def _create_masked_structure(
    cursor: Any, context: dict[str, Any], columns_by_table: dict[str, list[str]]
) -> None:
    for masked_schema in MASKED_SCHEMAS:
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(masked_schema)))
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(masked_schema)))
    for source_table in context["source_tables"]:
        source_schema, table_name = source_table.split(".")
        masked_schema = SCHEMA_MAPPING[source_schema]
        cursor.execute(
            sql.SQL("CREATE TABLE {} (LIKE {} INCLUDING ALL EXCLUDING DEFAULTS)").format(
                _qualified(masked_schema, table_name), _qualified(source_schema, table_name)
            )
        )
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
              AND column_default LIKE %s
            ORDER BY ordinal_position
            """,
            (source_schema, table_name, "nextval(%"),
        )
        for (column_name,) in cursor.fetchall():
            sequence_name = f"{table_name}_{column_name}_seq"
            cursor.execute(
                sql.SQL("CREATE SEQUENCE {} OWNED BY {}.{}").format(
                    _qualified(masked_schema, sequence_name),
                    _qualified(masked_schema, table_name), sql.Identifier(column_name),
                )
            )
            cursor.execute(
                sql.SQL("ALTER TABLE {} ALTER COLUMN {} SET DEFAULT nextval({}::regclass)").format(
                    _qualified(masked_schema, table_name), sql.Identifier(column_name),
                    sql.Literal(f"{masked_schema}.{sequence_name}"),
                )
            )
    for foreign_key in context["foreign_keys"]:
        masked_schema = SCHEMA_MAPPING[foreign_key["source_schema"]]
        definition = foreign_key["definition"]
        for source_schema, target_schema in SCHEMA_MAPPING.items():
            definition = re.sub(
                rf"(?i)(REFERENCES\s+){re.escape(source_schema)}\.",
                rf"\1{target_schema}.", definition,
            )
        cursor.execute(
            sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} {}").format(
                _qualified(masked_schema, foreign_key["source_table"]),
                sql.Identifier(foreign_key["constraint_name"]), sql.SQL(definition),
            )
        )


def _insert_masked_data(
    cursor: Any, context: dict[str, Any], columns_by_table: dict[str, list[str]],
    primary_keys: dict[str, list[str]], masked_data: dict[str, list[tuple[Any, ...]]],
    fail_after_tables: int | None = None,
) -> None:
    for position, source_table in enumerate(context["load_order"], start=1):
        source_schema, table_name = source_table.split(".")
        masked_schema = SCHEMA_MAPPING[source_schema]
        columns = columns_by_table[source_table]
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            _qualified(masked_schema, table_name),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        cursor.executemany(query, masked_data[source_table])
        for primary_key in primary_keys[source_table]:
            cursor.execute(
                "SELECT column_default FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name=%s",
                (masked_schema, table_name, primary_key),
            )
            default = cursor.fetchone()[0]
            if default and default.startswith("nextval("):
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE(max_value, 1), max_value IS NOT NULL) FROM (SELECT max(" +
                    sql.Identifier(primary_key).as_string(cursor.connection) +
                    ") AS max_value FROM " + _qualified(masked_schema, table_name).as_string(cursor.connection) + ") AS values_to_set",
                    (f"{masked_schema}.{table_name}", primary_key),
                )
        if fail_after_tables is not None and position >= fail_after_tables:
            raise MaskingPipelineError("Injected aggregate-only failure for rollback verification.")


def _column_metadata(cursor: Any, schemas: tuple[str, ...]) -> list[tuple[Any, ...]]:
    cursor.execute(
        """
        SELECT table_schema, table_name, column_name, ordinal_position, data_type, udt_name,
               character_maximum_length, numeric_precision, numeric_scale, is_nullable
        FROM information_schema.columns WHERE table_schema = ANY(%s)
        ORDER BY table_schema, table_name, ordinal_position
        """,
        (list(schemas),),
    )
    return cursor.fetchall()


def _normalized_column_metadata(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    reverse = {masked: source for source, masked in SCHEMA_MAPPING.items()}
    return sorted(
        (reverse.get(row[0], row[0]), *row[1:]) for row in rows
    )


def _constraint_signatures(cursor: Any, schemas: tuple[str, ...]) -> list[tuple[Any, ...]]:
    cursor.execute(
        """
        SELECT schema_def.nspname, table_def.relname, constraint_def.contype,
               ARRAY(
                   SELECT attribute_def.attname FROM unnest(constraint_def.conkey)
                   WITH ORDINALITY AS key_def(attnum, position)
                   JOIN pg_attribute AS attribute_def
                     ON attribute_def.attrelid = table_def.oid AND attribute_def.attnum = key_def.attnum
                   ORDER BY key_def.position
               ) AS source_columns,
               target_schema.nspname, target_table.relname,
               ARRAY(
                   SELECT attribute_def.attname FROM unnest(constraint_def.confkey)
                   WITH ORDINALITY AS key_def(attnum, position)
                   JOIN pg_attribute AS attribute_def
                     ON attribute_def.attrelid = target_table.oid AND attribute_def.attnum = key_def.attnum
                   ORDER BY key_def.position
               ) AS target_columns,
               CASE WHEN constraint_def.contype = 'c'
                    THEN pg_get_expr(constraint_def.conbin, constraint_def.conrelid)
                    ELSE NULL END
        FROM pg_constraint AS constraint_def
        JOIN pg_class AS table_def ON table_def.oid = constraint_def.conrelid
        JOIN pg_namespace AS schema_def ON schema_def.oid = table_def.relnamespace
        LEFT JOIN pg_class AS target_table ON target_table.oid = constraint_def.confrelid
        LEFT JOIN pg_namespace AS target_schema ON target_schema.oid = target_table.relnamespace
        WHERE schema_def.nspname = ANY(%s) AND constraint_def.contype IN ('p','u','f','c')
        ORDER BY schema_def.nspname, table_def.relname, constraint_def.contype, source_columns
        """,
        (list(schemas),),
    )
    reverse = {masked: source for source, masked in SCHEMA_MAPPING.items()}
    signatures = []
    for row in cursor.fetchall():
        source_schema, table_name, constraint_type, source_columns, target_schema, target_table, target_columns, expression = row
        signatures.append((
            reverse.get(source_schema, source_schema), table_name, constraint_type,
            tuple(source_columns or ()), reverse.get(target_schema, target_schema),
            target_table, tuple(target_columns or ()), expression,
        ))
    return sorted(signatures)


def _row_counts(cursor: Any, tables: list[str], *, masked: bool) -> dict[str, int]:
    counts = {}
    for table in tables:
        schema_name, table_name = table.split(".")
        actual_schema = SCHEMA_MAPPING[schema_name] if masked else schema_name
        cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(_qualified(actual_schema, table_name)))
        counts[table] = cursor.fetchone()[0]
    return counts


def _fetch_masked_rows(
    cursor: Any, tables: list[str], columns_by_table: dict[str, list[str]],
    primary_keys: dict[str, list[str]],
) -> dict[str, list[tuple[Any, ...]]]:
    rows = {}
    for table in tables:
        schema_name, table_name = table.split(".")
        query = sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
            sql.SQL(", ").join(map(sql.Identifier, columns_by_table[table])),
            _qualified(SCHEMA_MAPPING[schema_name], table_name),
            sql.SQL(", ").join(map(sql.Identifier, primary_keys[table])),
        )
        cursor.execute(query)
        rows[table] = cursor.fetchall()
    return rows


def _validate_no_cleartext(
    context: dict[str, Any], columns_by_table: dict[str, list[str]],
    source_data: dict[str, list[tuple[Any, ...]]], masked_data: dict[str, list[tuple[Any, ...]]],
    known_names: list[str],
) -> None:
    structured_rules = {
        "mask_person_name", "mask_email", "mask_phone", "mask_tax_code", "mask_iban",
        "mask_contact_value", "mask_postal_address", "shift_birth_date",
    }
    for table in context["source_tables"]:
        for column_index, column_name in enumerate(columns_by_table[table]):
            key = f"{table}.{column_name}"
            rule = context["registry_by_column"][key]["masking_rule"]
            for source_row, masked_row in zip(source_data[table], masked_data[table]):
                source_value, masked_value = source_row[column_index], masked_row[column_index]
                if rule in structured_rules and source_value not in (None, "") and source_value == masked_value:
                    raise MaskedValidationError(
                        f"A structured transformed value remained unchanged in column {key}."
                    )
                if rule == "redact_free_text" and masked_value not in (None, ""):
                    if redact_free_text(str(masked_value), known_names=known_names) != masked_value:
                        raise MaskedValidationError("Detectable PII remains in a masked free-text column.")
                if rule == "review_before_masking" and context["decision"]["strategy"] == "redact_detected_patterns":
                    if source_value not in (None, "") and source_value == masked_value:
                        raise MaskedValidationError("The approved ambiguous-column redaction did not alter a non-empty value.")


def _join_match_count(cursor: Any, foreign_key: dict[str, Any], *, masked: bool) -> int:
    source_schema = SCHEMA_MAPPING[foreign_key["source_schema"]] if masked else foreign_key["source_schema"]
    target_schema = SCHEMA_MAPPING[foreign_key["target_schema"]] if masked else foreign_key["target_schema"]
    conditions = [
        sql.SQL("child.{} = parent.{}").format(sql.Identifier(source), sql.Identifier(target))
        for source, target in zip(foreign_key["source_columns"], foreign_key["target_columns"])
    ]
    cursor.execute(
        sql.SQL("SELECT count(*) FROM {} AS child JOIN {} AS parent ON {}").format(
            _qualified(source_schema, foreign_key["source_table"]),
            _qualified(target_schema, foreign_key["target_table"]),
            sql.SQL(" AND ").join(conditions),
        )
    )
    return cursor.fetchone()[0]


def _validate_relationship_matches(cursor: Any, context: dict[str, Any]) -> None:
    for foreign_key in context["foreign_keys"]:
        if _join_match_count(cursor, foreign_key, masked=False) != _join_match_count(
            cursor, foreign_key, masked=True
        ):
            raise MaskedValidationError("A declared relationship changed its join count.")
    logical_queries = (
        (
            "SELECT count(*) FROM hr.reparti r JOIN hr.dipendenti d ON d.dipendente_id=r.responsabile_id",
            "SELECT count(*) FROM masked_hr.reparti r JOIN masked_hr.dipendenti d ON d.dipendente_id=r.responsabile_id",
        ),
        (
            "SELECT count(*) FROM billing.fatture f JOIN crm.clienti c ON c.cliente_id=f.cliente_id",
            "SELECT count(*) FROM masked_billing.fatture f JOIN masked_crm.clienti c ON c.cliente_id=f.cliente_id",
        ),
    )
    for source_query, masked_query in logical_queries:
        cursor.execute(source_query)
        source_count = cursor.fetchone()[0]
        cursor.execute(masked_query)
        if source_count != cursor.fetchone()[0]:
            raise MaskedValidationError("A confirmed logical relationship changed its match count.")


def _validate_required_consistency(cursor: Any) -> None:
    queries = (
        """
        SELECT count(*) FROM billing.sconti s
        JOIN crm.clienti c ON c.cod_fisc=s.cod_rif
        JOIN masked_billing.sconti ms ON ms.sconto_id=s.sconto_id
        JOIN masked_crm.clienti mc ON mc.cliente_id=c.cliente_id
        WHERE ms.cod_rif <> mc.cod_fisc
        """,
        """
        SELECT count(*) FROM billing.pagamenti p
        JOIN crm.clienti c ON lower(c.email)=lower(p.rif_esterno)
        JOIN masked_billing.pagamenti mp ON mp.pagamento_id=p.pagamento_id
        JOIN masked_crm.clienti mc ON mc.cliente_id=c.cliente_id
        WHERE mp.rif_esterno <> mc.email
        """,
        """
        SELECT count(*) FROM hr.buste_paga b
        JOIN hr.dipendenti d ON d.dipendente_id=b.dipendente_id AND d.iban=b.iban_accredito
        JOIN masked_hr.buste_paga mb ON mb.busta_id=b.busta_id
        JOIN masked_hr.dipendenti md ON md.dipendente_id=d.dipendente_id
        WHERE mb.iban_accredito <> md.iban
        """,
    )
    for query in queries:
        cursor.execute(query)
        if cursor.fetchone()[0] != 0:
            raise MaskedValidationError("A required consistency group produced mismatched outputs.")


def validate_masked_database(
    cursor: Any, context: dict[str, Any], columns_by_table: dict[str, list[str]],
    primary_keys: dict[str, list[str]], source_data: dict[str, list[tuple[Any, ...]]] | None = None,
    transform_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT table_schema, table_name FROM information_schema.tables
        WHERE table_type='BASE TABLE' AND table_schema = ANY(%s)
        ORDER BY table_schema, table_name
        """,
        (list(MASKED_SCHEMAS),),
    )
    masked_tables = cursor.fetchall()
    if len(masked_tables) != 20:
        raise MaskedValidationError("Exactly 20 masked tables are required.")
    source_counts = _row_counts(cursor, context["source_tables"], masked=False)
    masked_counts = _row_counts(cursor, context["source_tables"], masked=True)
    if source_counts != masked_counts:
        raise MaskedValidationError("Source and masked row counts differ.")
    if _normalized_column_metadata(_column_metadata(cursor, SOURCE_SCHEMAS)) != _normalized_column_metadata(_column_metadata(cursor, MASKED_SCHEMAS)):
        raise MaskedValidationError("Masked column metadata differs from source metadata.")
    if _constraint_signatures(cursor, SOURCE_SCHEMAS) != _constraint_signatures(cursor, MASKED_SCHEMAS):
        raise MaskedValidationError("Masked PK, FK, UNIQUE or CHECK constraints differ from source constraints.")

    cursor.execute(
        """
        SELECT count(*) FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_schema=kcu.constraint_schema AND tc.constraint_name=kcu.constraint_name
        WHERE tc.constraint_type='FOREIGN KEY' AND (
          (tc.table_schema='masked_hr' AND tc.table_name='reparti' AND kcu.column_name='responsabile_id') OR
          (tc.table_schema='masked_billing' AND tc.table_name='fatture' AND kcu.column_name='cliente_id')
        )
        """
    )
    if cursor.fetchone()[0] != 0:
        raise MaskedValidationError("A logical relationship was incorrectly promoted to a foreign key.")
    _validate_relationship_matches(cursor, context)
    _validate_required_consistency(cursor)

    masked_rows = _fetch_masked_rows(
        cursor, context["source_tables"], columns_by_table, primary_keys
    )
    if source_data is not None and transform_summary is not None:
        _validate_no_cleartext(
            context, columns_by_table, source_data, masked_rows,
            transform_summary["known_names"],
        )
    table_checksums = {}
    for table in context["source_tables"]:
        source_schema, table_name = table.split(".")
        table_checksums[f"{SCHEMA_MAPPING[source_schema]}.{table_name}"] = table_checksum(
            SCHEMA_MAPPING[source_schema], table_name, columns_by_table[table], masked_rows[table]
        )
    return {
        "source_counts": source_counts, "masked_counts": masked_counts,
        "table_checksums": dict(sorted(table_checksums.items())),
        "masked_rows": masked_rows,
        "validations": [
            "20_masked_tables", "row_counts", "column_names_order_types_nullability",
            "primary_keys", "foreign_keys", "unique_constraints", "check_constraints",
            "declared_join_counts", "logical_relationship_match_counts",
            "logical_relationships_not_promoted", "required_consistency_groups",
            "no_detectable_cleartext_pii",
        ],
    }


def _source_checksums(
    context: dict[str, Any], columns_by_table: dict[str, list[str]],
    source_data: dict[str, list[tuple[Any, ...]]],
) -> dict[str, str]:
    return {
        table: table_checksum(table.split(".")[0], table.split(".")[1], columns_by_table[table], source_data[table])
        for table in context["source_tables"]
    }


def _build_manifest(
    context: dict[str, Any], validation: dict[str, Any],
    transform_summary: dict[str, Any],
) -> dict[str, Any]:
    collision_records = transform_summary["collision_details"]
    deterministic = {
        "format_version": 1,
        "git_commit": current_git_commit(),
        "primary_algorithm": "HMAC-SHA-256",
        "final_status": "success",
        "tables_processed": len(context["source_tables"]),
        "load_order": context["load_order"],
        "source_rows_by_table": validation["source_counts"],
        "masked_rows_by_table": validation["masked_counts"],
        "transformed_columns": transform_summary["transformed_columns"],
        "preserved_columns": transform_summary["preserved_columns"],
        "rules_applied": transform_summary["rule_counts"],
        "consistency_groups_used": sorted(_load_yaml(CONSISTENCY_GROUPS_PATH)["groups"]),
        "collision_statistics": {
            "values_processed": sum(item["values_processed"] for item in collision_records.values()),
            "collisions_detected": sum(item["collisions_detected"] for item in collision_records.values()),
            "collisions_resolved": sum(item["collisions_resolved"] for item in collision_records.values()),
            "maximum_attempts": max((item["maximum_attempts"] for item in collision_records.values()), default=0),
        },
        "ambiguous_column_strategy": {
            "column": "billing.pagamenti.riferimento_bancario",
            "strategy": context["decision"]["strategy"],
            "review_status": context["decision"]["review_status"],
            "residual_risk_documented": bool(context["decision"].get("residual_risk")),
        },
        "validations": validation["validations"] + [
            "source_schemas_unchanged", "manifest_contains_no_values_or_secret"
        ],
        "table_checksums": validation["table_checksums"],
        "checksum_canonicalization": {
            "algorithm": "SHA-256",
            "row_order": "explicit_primary_key_order",
            "null": "typed_null_marker",
            "date_datetime": "ISO-8601",
            "decimal": "fixed_point_string",
            "columns": "ordinal_position",
        },
    }
    return finalize_manifest(deterministic)


def dry_run_plan() -> dict[str, Any]:
    with get_connection() as connection, connection.cursor() as cursor:
        context = validate_preconditions(cursor)
        columns_by_table, _, source_data = _fetch_all_source_data(
            cursor, context["source_tables"]
        )
        _, _, collision_details = _prepare_batch_mappings(
            context, columns_by_table, source_data
        )
    return {
        "tables": len(context["source_tables"]), "load_order": context["load_order"],
        "ambiguous_strategy": context["decision"]["strategy"],
        "batch_sets": len(collision_details), "writes_performed": False,
    }


def apply_masking(
    *, manifest_path: Path = MANIFEST_PATH,
    fail_after_tables: int | None = None,
) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            context = validate_preconditions(cursor)
            columns_by_table, primary_keys, source_data = _fetch_all_source_data(
                cursor, context["source_tables"]
            )
            source_before = _source_checksums(context, columns_by_table, source_data)
            masked_data, transform_summary = _transform_data(
                context, columns_by_table, source_data
            )
            _create_masked_structure(cursor, context, columns_by_table)
            _insert_masked_data(
                cursor, context, columns_by_table, primary_keys, masked_data,
                fail_after_tables=fail_after_tables,
            )
            validation = validate_masked_database(
                cursor, context, columns_by_table, primary_keys,
                source_data=source_data, transform_summary=transform_summary,
            )
            _, _, source_after_data = _fetch_all_source_data(
                cursor, context["source_tables"]
            )
            if source_before != _source_checksums(context, columns_by_table, source_after_data):
                raise MaskedValidationError("Source schemas changed during masking.")
            manifest = _build_manifest(context, validation, transform_summary)
    write_manifest(manifest, manifest_path)
    return manifest


def validate_only() -> dict[str, Any]:
    with get_connection() as connection, connection.cursor() as cursor:
        context = validate_preconditions(cursor)
        columns_by_table, primary_keys, source_data = _fetch_all_source_data(
            cursor, context["source_tables"]
        )
        names = _known_names(context["records"], columns_by_table, source_data)
        return validate_masked_database(
            cursor, context, columns_by_table, primary_keys,
            source_data=source_data, transform_summary={"known_names": names},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Transactional masked database pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and calculate the plan without writes")
    mode.add_argument("--validate-only", action="store_true", help="Validate an existing masked database without writes")
    args = parser.parse_args()
    if args.dry_run:
        plan = dry_run_plan()
        print(
            f"Dry run valid: {plan['tables']} tables, {plan['batch_sets']} deterministic batches, "
            f"ambiguous strategy={plan['ambiguous_strategy']}; writes=0."
        )
        print("Load order: " + ", ".join(plan["load_order"]))
    elif args.validate_only:
        result = validate_only()
        print(
            f"Masked database valid: {len(result['masked_counts'])} tables, "
            f"{sum(result['masked_counts'].values())} rows."
        )
    else:
        manifest = apply_masking()
        print(
            f"Masked database loaded: {manifest['tables_processed']} tables; "
            f"global checksum={manifest['global_checksum']}."
        )
        print(f"Written: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
