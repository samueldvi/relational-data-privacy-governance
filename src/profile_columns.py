"""Deterministic, privacy-safe profiling for PostgreSQL source columns."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from psycopg import sql

from src.domain.identifiers import is_valid_italian_iban, is_valid_tax_code
from src.domain.profiling.normalizers import (
    normalize_email,
    normalize_iban,
    normalize_name,
    normalize_phone,
    normalize_tax_code,
    normalize_text,
)
from src.infrastructure.database.connection import get_connection
from src.inventory import SOURCE_SCHEMAS, collect_inventory


OUTPUT_PATH = Path("output/profiling_results.json")
MAX_SAMPLES = 20

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"\+39\s*000\s*\d{7}")
TAX_CODE_RE = re.compile(r"\b[A-Z0-9]{16}\b", re.IGNORECASE)
IBAN_RE = re.compile(r"\bIT[0-9A-Z\s]{25,32}\b", re.IGNORECASE)
POSTAL_CODE_RE = re.compile(r"^\d{5}$")
PARTIAL_CARD_RE = re.compile(r"(?:\d[ -]?){4}(?:[*Xx][*Xx -]{2,})(?:\d[ -]?){4}")

PATTERN_ORDER = (
    "email", "phone", "italian_tax_code", "italian_iban", "birth_date",
    "postal_address", "postal_code", "partial_card", "bank_reference",
    "person_name", "surname", "free_text_pii", "email_template",
    "technical_identifier", "aggregate_value",
)

SAMPLE_ELIGIBLE_PATTERNS = {
    "email", "phone", "italian_tax_code", "italian_iban", "birth_date",
    "postal_address", "postal_code", "partial_card", "person_name", "surname",
    "free_text_pii", "email_template",
}

PRIVACY_EVIDENCE_PATTERNS = SAMPLE_ELIGIBLE_PATTERNS - {"email_template"}

METADATA_KEYS = {
    "schema_name", "table_name", "column_name", "ordinal_position", "data_type",
    "row_count", "non_null_count", "null_count", "null_percentage",
    "distinct_count", "uniqueness_percentage", "minimum_length", "maximum_length",
    "average_length", "minimum_value", "maximum_value", "detected_patterns",
    "pattern_match_counts", "pattern_match_percentages", "sample_values",
    "sample_redaction_applied", "cross_table_matches", "profiling_notes",
}


def _qualified_identifier(schema: str, table: str) -> sql.Composed:
    return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))


def _fetch_values(cursor: Any, schema: str, table: str, column: str) -> list[Any]:
    identifier = sql.Identifier(column)
    cursor.execute(
        sql.SQL("SELECT {column} FROM {table} ORDER BY {column}::text NULLS LAST").format(
            column=identifier, table=_qualified_identifier(schema, table)
        )
    )
    return [row[0] for row in cursor.fetchall()]


def _fetch_known_names(cursor: Any) -> tuple[set[str], set[str], set[str]]:
    first_names: set[str] = set()
    surnames: set[str] = set()
    full_names: set[str] = set()
    for query in (
        "SELECT nome, cognome FROM crm.clienti",
        "SELECT nome, cognome FROM hr.dipendenti",
    ):
        cursor.execute(query)
        for first_name, surname in cursor.fetchall():
            first_names.add(normalize_name(first_name))
            surnames.add(normalize_name(surname))
            full_names.add(normalize_name(f"{first_name} {surname}"))
    for query in (
        "SELECT nome_ref FROM crm.referenti_commerciali",
        "SELECT docente FROM hr.formazione",
    ):
        cursor.execute(query)
        full_names.update(normalize_name(row[0]) for row in cursor.fetchall())
    return first_names, surnames, full_names


def _contains_known_name(
    value: str, first_names: set[str], surnames: set[str], full_names: set[str]
) -> bool:
    normalized = normalize_name(value)
    if normalized in first_names or normalized in surnames or normalized in full_names:
        return True
    padded = f" {normalized} "
    candidates = full_names | {name for name in first_names | surnames if len(name) >= 4}
    return any(f" {candidate} " in padded for candidate in candidates)


def _valid_tax_codes_in(value: str) -> list[str]:
    candidates = [normalize_tax_code(match.group(0)) for match in TAX_CODE_RE.finditer(value)]
    return [candidate for candidate in candidates if is_valid_tax_code(candidate)]


def _valid_ibans_in(value: str) -> list[str]:
    candidates = [normalize_iban(match.group(0)) for match in IBAN_RE.finditer(value)]
    return [candidate for candidate in candidates if is_valid_italian_iban(candidate)]


def _pattern_flags(
    value: Any,
    schema: str,
    table: str,
    column: str,
    data_type: str,
    first_names: set[str],
    surnames: set[str],
    full_names: set[str],
) -> set[str]:
    flags: set[str] = set()
    text = str(value)
    lowered_column = column.lower()
    lowered_table = table.lower()

    if EMAIL_RE.search(text):
        flags.add("email")
    if PHONE_RE.search(text):
        flags.add("phone")
    if _valid_tax_codes_in(text):
        flags.add("italian_tax_code")
    if _valid_ibans_in(text):
        flags.add("italian_iban")
    if (
        data_type == "date" and "nascita" in lowered_column
        and isinstance(value, date) and date(1900, 1, 1) <= value <= date(2020, 12, 31)
    ):
        flags.add("birth_date")
    if lowered_column in {"via", "citta", "provincia"} and text.strip():
        flags.add("postal_address")
    if lowered_column == "cap" and POSTAL_CODE_RE.fullmatch(text.strip()):
        flags.add("postal_code")
    if PARTIAL_CARD_RE.search(text):
        flags.add("partial_card")
    if any(token in lowered_column for token in ("bancario", "riferimento", "iban")):
        flags.add("bank_reference")

    direct_name_columns = {"nome", "nome_ref", "docente", "intestatario"}
    if lowered_column in direct_name_columns or _contains_known_name(
        text, first_names, surnames, full_names
    ):
        flags.add("person_name")
    if lowered_column == "cognome" or normalize_name(text) in surnames:
        flags.add("surname")

    free_text_columns = {"testo", "commento", "testo_sollecito"}
    embedded_pii = bool(flags & {"email", "phone", "italian_tax_code", "italian_iban", "person_name", "surname"})
    if lowered_column in free_text_columns and embedded_pii:
        flags.add("free_text_pii")
    if "template" in lowered_column and "@" in text and "{{" in text and "}}" in text:
        flags.add("email_template")
    if lowered_column.endswith("_id") and data_type in {"bigint", "integer", "smallint"}:
        flags.add("technical_identifier")
    if lowered_table == "report_mensili" or lowered_column.startswith("totale_"):
        flags.add("aggregate_value")
    return flags


def _redact_email(match: re.Match[str]) -> str:
    local, domain = match.group(0).split("@", 1)
    return f"{local[:1]}***@{domain.lower()}"


def _redact_phone(match: re.Match[str]) -> str:
    normalized = normalize_phone(match.group(0))
    return f"+39******{normalized[-3:]}"


def _redact_value(
    value: Any,
    patterns: set[str],
    column: str,
    known_names: set[str],
) -> tuple[str | None, bool]:
    text = str(value)
    original = text
    if "email_template" in patterns:
        return text, False
    if "birth_date" in patterns and isinstance(value, date):
        return f"{value.year:04d}-**-**", True
    if "postal_address" in patterns or "postal_code" in patterns:
        return "[REDACTED_ADDRESS]", True
    if patterns & {"person_name", "surname"} and column in {
        "nome", "cognome", "nome_ref", "docente", "intestatario"
    }:
        return "[REDACTED_NAME]", True

    text = EMAIL_RE.sub(_redact_email, text)
    text = PHONE_RE.sub(_redact_phone, text)
    for candidate in _valid_tax_codes_in(text):
        text = re.sub(re.escape(candidate), candidate[:6] + ("*" * 10), text, flags=re.IGNORECASE)
    for candidate in _valid_ibans_in(text):
        text = re.sub(re.escape(candidate), "IT" + ("*" * 25), text, flags=re.IGNORECASE)
    if patterns & {"free_text_pii", "person_name", "surname"}:
        for name in sorted(known_names, key=lambda item: (-len(item), item)):
            if len(name) < 4:
                continue
            text = re.sub(rf"\b{re.escape(name)}\b", "[REDACTED_NAME]", text, flags=re.IGNORECASE)

    if text == original and patterns & {
        "email", "phone", "italian_tax_code", "italian_iban", "free_text_pii"
    }:
        return None, False
    return text, text != original


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    return value


def _profile_column(
    metadata: dict[str, Any],
    values: list[Any],
    first_names: set[str],
    surnames: set[str],
    full_names: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    non_null_values = [value for value in values if value is not None]
    distinct_values = sorted(set(non_null_values), key=lambda value: str(value))
    row_count = len(values)
    non_null_count = len(non_null_values)
    lengths = [len(str(value)) for value in non_null_values]
    flags_by_value = [
        _pattern_flags(
            value, metadata["schema_name"], metadata["table_name"], metadata["column_name"],
            metadata["data_type"], first_names, surnames, full_names,
        )
        for value in non_null_values
    ]
    pattern_counts = {
        pattern: sum(pattern in flags for flags in flags_by_value)
        for pattern in PATTERN_ORDER
    }
    detected_patterns = [pattern for pattern in PATTERN_ORDER if pattern_counts[pattern] > 0]
    pattern_counts = {pattern: pattern_counts[pattern] for pattern in detected_patterns}
    pattern_percentages = {
        pattern: round(count * 100 / non_null_count, 2) if non_null_count else 0.0
        for pattern, count in pattern_counts.items()
    }

    notes = ["Profiling tecnico: nessuna classificazione PII definitiva assegnata."]
    if "email_template" in detected_patterns:
        notes.append("Possibile falso positivo: struttura email con placeholder, non prova di PII reale.")
    if "free_text_pii" in detected_patterns:
        notes.append("Campioni di testo libero redatti prima della serializzazione.")
    if metadata["column_name"] in {"cod_rif", "rif_esterno"}:
        notes.append("Nome colonna non informativo: evidenza derivata dalla struttura dei valori.")

    sample_values: list[str] = []
    redaction_applied = False
    redacted_sample_count = 0
    if set(detected_patterns) & SAMPLE_ELIGIBLE_PATTERNS:
        all_known_names = first_names | surnames | full_names
        for value in distinct_values:
            flags = _pattern_flags(
                value, metadata["schema_name"], metadata["table_name"], metadata["column_name"],
                metadata["data_type"], first_names, surnames, full_names,
            )
            redacted, applied = _redact_value(value, flags, metadata["column_name"], all_known_names)
            if redacted is not None and redacted not in sample_values:
                sample_values.append(redacted)
                redaction_applied = redaction_applied or applied
                redacted_sample_count += int(applied)
            if len(sample_values) == MAX_SAMPLES:
                break

    supports_range = metadata["data_type"] in {
        "smallint", "integer", "bigint", "numeric", "real", "double precision",
        "date", "timestamp without time zone", "timestamp with time zone",
    }
    sensitive_range = "birth_date" in detected_patterns
    minimum_value = _json_scalar(min(non_null_values)) if non_null_values and supports_range and not sensitive_range else None
    maximum_value = _json_scalar(max(non_null_values)) if non_null_values and supports_range and not sensitive_range else None

    profile = {
        "schema_name": metadata["schema_name"],
        "table_name": metadata["table_name"],
        "column_name": metadata["column_name"],
        "ordinal_position": metadata["ordinal_position"],
        "data_type": metadata["data_type"],
        "row_count": row_count,
        "non_null_count": non_null_count,
        "null_count": row_count - non_null_count,
        "null_percentage": round((row_count - non_null_count) * 100 / row_count, 2) if row_count else 0.0,
        "distinct_count": len(distinct_values),
        "uniqueness_percentage": round(len(distinct_values) * 100 / non_null_count, 2) if non_null_count else 0.0,
        "minimum_length": min(lengths) if lengths else None,
        "maximum_length": max(lengths) if lengths else None,
        "average_length": round(sum(lengths) / len(lengths), 2) if lengths else None,
        "minimum_value": minimum_value,
        "maximum_value": maximum_value,
        "detected_patterns": detected_patterns,
        "pattern_match_counts": pattern_counts,
        "pattern_match_percentages": pattern_percentages,
        "sample_values": sample_values,
        "sample_redaction_applied": redaction_applied,
        "redacted_sample_count": redacted_sample_count,
        "cross_table_matches": [],
        "profiling_notes": notes,
    }
    internal = {"values": non_null_values, "flags_by_value": flags_by_value}
    return profile, internal


def _domain_values(
    values: list[Any], domain: str, first_names: set[str], surnames: set[str], full_names: set[str]
) -> set[str]:
    normalizers: dict[str, Callable[[str], str]] = {
        "email": normalize_email,
        "italian_tax_code": normalize_tax_code,
        "italian_iban": normalize_iban,
        "phone": normalize_phone,
        "person_name": normalize_name,
        "surname": normalize_name,
    }
    result = set()
    for value in values:
        text = str(value)
        if domain == "email" and EMAIL_RE.fullmatch(text.strip()):
            result.add(normalize_email(text))
        elif domain == "italian_tax_code" and is_valid_tax_code(normalize_tax_code(text)):
            result.add(normalize_tax_code(text))
        elif domain == "italian_iban" and is_valid_italian_iban(normalize_iban(text)):
            result.add(normalize_iban(text))
        elif domain == "phone" and PHONE_RE.fullmatch(text.strip()):
            result.add(normalize_phone(text))
        elif domain == "person_name" and normalize_name(text) in first_names | full_names:
            result.add(normalize_name(text))
        elif domain == "surname" and normalize_name(text) in surnames:
            result.add(normalize_name(text))
    return result


def _add_cross_table_matches(
    profiles: list[dict[str, Any]],
    internal_data: dict[tuple[str, str, str], dict[str, Any]],
    first_names: set[str],
    surnames: set[str],
    full_names: set[str],
) -> None:
    domains = ("email", "italian_tax_code", "italian_iban", "phone", "person_name", "surname")
    profile_lookup = {
        (profile["schema_name"], profile["table_name"], profile["column_name"]): profile
        for profile in profiles
    }
    for source_key, source_profile in sorted(profile_lookup.items()):
        matches = []
        for domain in domains:
            if domain not in source_profile["detected_patterns"]:
                continue
            source_values = _domain_values(
                internal_data[source_key]["values"], domain, first_names, surnames, full_names
            )
            if not source_values:
                continue
            for target_key, target_profile in sorted(profile_lookup.items()):
                if source_key == target_key or domain not in target_profile["detected_patterns"]:
                    continue
                target_values = _domain_values(
                    internal_data[target_key]["values"], domain, first_names, surnames, full_names
                )
                common = source_values & target_values
                if not common:
                    continue
                percentage = len(common) * 100 / len(source_values)
                confidence = "high" if percentage >= 80 else "medium" if percentage >= 25 else "low"
                matches.append({
                    "target_column": ".".join(target_key),
                    "pattern": domain,
                    "source_non_null_count": len(internal_data[source_key]["values"]),
                    "source_distinct_count": len(source_values),
                    "matched_distinct_count": len(common),
                    "match_percentage": round(percentage, 2),
                    "normalization": {
                        "email": "trim_lowercase", "italian_tax_code": "trim_uppercase",
                        "italian_iban": "remove_spaces_uppercase", "phone": "digits_with_optional_plus",
                        "person_name": "trim_lowercase_collapse_spaces", "surname": "trim_lowercase_collapse_spaces",
                    }[domain],
                    "evidence": f"{len(common)}/{len(source_values)} valori distinti normalizzati in comune",
                    "technical_confidence": confidence,
                })
        source_profile["cross_table_matches"] = sorted(
            matches, key=lambda item: (item["pattern"], item["target_column"])
        )


def build_profiling_results() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            inventory = collect_inventory(connection)
            first_names, surnames, full_names = _fetch_known_names(cursor)
            profiles = []
            internal_data = {}
            for metadata in inventory:
                key = (metadata["schema_name"], metadata["table_name"], metadata["column_name"])
                values = _fetch_values(cursor, *key)
                profile, internal = _profile_column(
                    metadata, values, first_names, surnames, full_names
                )
                profiles.append(profile)
                internal_data[key] = internal
            _add_cross_table_matches(
                profiles, internal_data, first_names, surnames, full_names
            )

    pattern_evidence_columns = sum(bool(profile["detected_patterns"]) for profile in profiles)
    suspicious_columns = sum(
        bool(set(profile["detected_patterns"]) & PRIVACY_EVIDENCE_PATTERNS)
        for profile in profiles
    )
    redacted_samples = sum(profile["redacted_sample_count"] for profile in profiles)
    detected_patterns = sorted({
        pattern for profile in profiles for pattern in profile["detected_patterns"]
    }, key=PATTERN_ORDER.index)
    return {
        "metadata": {
            "source_schemas": list(SOURCE_SCHEMAS),
            "column_count": len(profiles),
            "suspicious_column_count": suspicious_columns,
            "pattern_evidence_column_count": pattern_evidence_columns,
            "redacted_sample_count": redacted_samples,
            "maximum_samples_per_column": MAX_SAMPLES,
            "detected_patterns": detected_patterns,
            "classification_assigned": False,
        },
        "columns": profiles,
    }


def write_profiling_results(results: dict[str, Any], output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output_path.write_text(serialized, encoding="utf-8")


def generate_profiling(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    results = build_profiling_results()
    write_profiling_results(results, output_path)
    return results


def main() -> None:
    results = generate_profiling()
    metadata = results["metadata"]
    print(
        f"Profiled {metadata['column_count']} columns across "
        f"{len(metadata['source_schemas'])} source schemas; "
        f"{metadata['pattern_evidence_column_count']} columns contain technical pattern evidence, "
        f"of which {metadata['suspicious_column_count']} contain privacy-compatible patterns."
    )
    print(
        f"Patterns: {', '.join(metadata['detected_patterns'])}; "
        f"redacted samples: {metadata['redacted_sample_count']}."
    )
    print(f"Written: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
