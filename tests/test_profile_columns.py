from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.db import get_connection
from src.generate_data import TABLE_COLUMNS, dataset_digest
from src.profile_columns import METADATA_KEYS, generate_profiling


@pytest.fixture(scope="module")
def profiling(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    output_path = tmp_path_factory.mktemp("profiling") / "profiling_results.json"
    results = generate_profiling(output_path)
    return output_path, results


def indexed(results: dict) -> dict[tuple[str, str, str], dict]:
    return {(row["schema_name"], row["table_name"], row["column_name"]): row for row in results["columns"]}


def test_profiles_all_source_columns_with_required_metrics(profiling: tuple[Path, dict]) -> None:
    _, results = profiling
    assert results["metadata"]["column_count"] == 109
    assert len(results["columns"]) == 109
    assert all(METADATA_KEYS <= set(row) for row in results["columns"])
    assert {row["schema_name"] for row in results["columns"]} == {"billing", "crm", "hr"}
    assert not any(row["schema_name"].startswith("masked_") for row in results["columns"])


def test_columns_patterns_and_matches_are_deterministically_sorted(profiling: tuple[Path, dict]) -> None:
    _, results = profiling
    order = [(row["schema_name"], row["table_name"], row["ordinal_position"]) for row in results["columns"]]
    assert order == sorted(order)
    for row in results["columns"]:
        assert row["detected_patterns"] == sorted(
            row["detected_patterns"], key=results["metadata"]["detected_patterns"].index
        )
        match_order = [(match["pattern"], match["target_column"]) for match in row["cross_table_matches"]]
        assert match_order == sorted(match_order)


def test_output_is_byte_identical_between_runs(profiling: tuple[Path, dict]) -> None:
    output_path, _ = profiling
    first = output_path.read_bytes()
    generate_profiling(output_path)
    assert first == output_path.read_bytes()


def test_samples_are_limited_and_sensitive_structures_are_redacted(profiling: tuple[Path, dict]) -> None:
    output_path, results = profiling
    serialized_samples = json.dumps([sample for row in results["columns"] for sample in row["sample_values"]])
    assert all(len(row["sample_values"]) <= 20 for row in results["columns"])
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT email, telefono, cod_fisc FROM crm.clienti")
        sensitive_values = [str(value) for row in cursor.fetchall() for value in row if value]
        cursor.execute("SELECT iban FROM hr.dipendenti")
        sensitive_values.extend(row[0] for row in cursor.fetchall())
        cursor.execute("SELECT iban FROM billing.coordinate_bancarie")
        sensitive_values.extend(row[0] for row in cursor.fetchall())
    full_output = output_path.read_text(encoding="utf-8")
    assert not any(value in serialized_samples for value in sensitive_values)
    assert not any(value in full_output for value in sensitive_values)
    assert "***@example.test" in serialized_samples
    assert "+39******" in serialized_samples
    assert "**********" in serialized_samples
    assert "IT*************************" in serialized_samples


def test_free_text_is_detected_and_never_exported_complete(profiling: tuple[Path, dict]) -> None:
    output_path, results = profiling
    profiles = indexed(results)
    for key in (
        ("crm", "note_cliente", "testo"),
        ("hr", "valutazioni", "commento"),
        ("billing", "solleciti", "testo_sollecito"),
    ):
        assert "free_text_pii" in profiles[key]["detected_patterns"]
        assert profiles[key]["sample_redaction_applied"] is True
    output = output_path.read_text(encoding="utf-8")
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT testo FROM crm.note_cliente")
        originals = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT commento FROM hr.valutazioni WHERE commento LIKE '%@example.test%'")
        originals.extend(row[0] for row in cursor.fetchall())
        cursor.execute("SELECT testo_sollecito FROM billing.solleciti")
        originals.extend(row[0] for row in cursor.fetchall())
    assert not any(value in output for value in originals)


def test_expected_structured_patterns_are_detected(profiling: tuple[Path, dict]) -> None:
    _, results = profiling
    profiles = indexed(results)
    assert "email" in profiles[("crm", "clienti", "email")]["detected_patterns"]
    assert "italian_tax_code" in profiles[("crm", "clienti", "cod_fisc")]["detected_patterns"]
    assert "italian_iban" in profiles[("hr", "dipendenti", "iban")]["detected_patterns"]


def test_misleading_columns_are_detected_and_cross_matched(profiling: tuple[Path, dict]) -> None:
    _, results = profiling
    profiles = indexed(results)
    tax_trap = profiles[("billing", "sconti", "cod_rif")]
    email_trap = profiles[("billing", "pagamenti", "rif_esterno")]
    assert "italian_tax_code" in tax_trap["detected_patterns"]
    assert "email" in email_trap["detected_patterns"]
    tax_match = next(
        match for match in tax_trap["cross_table_matches"] if match["target_column"] == "crm.clienti.cod_fisc"
    )
    email_match = next(
        match for match in email_trap["cross_table_matches"] if match["target_column"] == "crm.clienti.email"
    )
    assert tax_match["match_percentage"] == 100.0
    assert email_match["match_percentage"] == 100.0
    assert tax_match["technical_confidence"] == "high"
    assert email_match["technical_confidence"] == "high"


def test_email_template_is_flagged_as_possible_false_positive(profiling: tuple[Path, dict]) -> None:
    _, results = profiling
    profile = indexed(results)[("crm", "campagne", "email_template")]
    assert "email_template" in profile["detected_patterns"]
    assert "email" not in profile["detected_patterns"]
    assert any("falso positivo" in note.lower() for note in profile["profiling_notes"])


def test_json_contains_no_credentials_or_final_classification(profiling: tuple[Path, dict]) -> None:
    output_path, results = profiling
    output = output_path.read_text(encoding="utf-8").lower()
    assert results["metadata"]["classification_assigned"] is False
    assert not any(key in output for key in ("postgres_password", "masking_secret", "postgresql://", "dbname="))
    assert not any("classification" in row or "pii_category" in row for row in results["columns"])


def test_profiler_does_not_modify_source_database(tmp_path: Path) -> None:
    def snapshot() -> tuple[tuple[str, ...], str]:
        data = {}
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name IN ('crm', 'hr', 'billing', 'masked_crm', 'masked_hr', 'masked_billing')
                ORDER BY schema_name
            """)
            schemas = tuple(row[0] for row in cursor.fetchall())
            for table, columns in TABLE_COLUMNS.items():
                cursor.execute(f"SELECT * FROM {table} ORDER BY {columns[0]}")
                data[table] = cursor.fetchall()
        return schemas, dataset_digest(data)

    before = snapshot()
    generate_profiling(tmp_path / "profile.json")
    after = snapshot()
    assert before == after


def test_module_command_runs_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.profile_columns"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Profiled 109 columns" in result.stdout
