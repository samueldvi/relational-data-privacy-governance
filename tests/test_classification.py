from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.classify import (
    ALLOWED_CATEGORIES,
    ALLOWED_REVIEW_STATUSES,
    DOMAINS_PATH,
    REGISTRY_PATH,
    REQUIRED_FIELDS,
    generate_classification,
    validate_registry,
)
from src.db import get_connection
from src.generate_data import TABLE_COLUMNS, dataset_digest
from src.generate_docs import render_classification_markdown


@pytest.fixture(scope="module")
def registry() -> tuple[list[dict], dict[str, dict]]:
    records = generate_classification()
    return records, {
        f"{record['schema_name']}.{record['table_name']}.{record['column_name']}": record for record in records
    }


def test_registry_has_complete_coverage_and_required_fields(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, _ = registry
    assert len(records) == 109
    assert len({(r["schema_name"], r["table_name"], r["column_name"]) for r in records}) == 109
    assert all(REQUIRED_FIELDS <= set(record) for record in records)
    for record in records:
        assert record["pii_category"]
        assert record["data_domain"]
        assert record["data_subject"]
        assert record["confidence"] is not None
        assert record["rationale"]
        assert record["review_status"]


def test_values_use_allowed_vocabularies(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, _ = registry
    assert {r["pii_category"] for r in records} <= ALLOWED_CATEGORIES
    assert {r["review_status"] for r in records} <= ALLOWED_REVIEW_STATUSES
    assert all(0 <= r["confidence"] <= 1 for r in records)


def test_data_domains_are_complete_and_referenced(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, _ = registry
    domains = yaml.safe_load(DOMAINS_PATH.read_text(encoding="utf-8"))["domains"]
    required_domain_fields = {
        "description",
        "default_pii_category",
        "normalization",
        "risk",
        "planned_transformation",
        "limitations",
        "synthetic_examples",
    }
    assert len(domains) >= 18
    assert all(required_domain_fields <= set(domain) for domain in domains.values())
    assert {record["data_domain"] for record in records} <= set(domains)


@pytest.mark.parametrize(
    ("key", "category", "domain", "subject", "status"),
    [
        ("billing.sconti.cod_rif", "PII-nascosta", "italian_tax_code", "customer", "confirmed"),
        ("billing.pagamenti.rif_esterno", "PII-nascosta", "email_address", "customer", "confirmed"),
        ("crm.campagne.email_template", "Non-PII", "business_metadata", "not_applicable", "false_positive_confirmed"),
        ("crm.note_cliente.testo", "PII-nascosta", "free_text_with_pii", "customer", "auto_proposed"),
        ("hr.valutazioni.commento", "PII-nascosta", "free_text_with_pii", "employee", "auto_proposed"),
        ("billing.solleciti.testo_sollecito", "PII-nascosta", "free_text_with_pii", "customer", "auto_proposed"),
        ("crm.clienti.data_nascita", "PII-indiretta", "birth_date", "customer", "auto_proposed"),
    ],
)
def test_mandatory_cases(
    registry: tuple[list[dict], dict[str, dict]],
    key: str,
    category: str,
    domain: str,
    subject: str,
    status: str,
) -> None:
    _, indexed = registry
    record = indexed[key]
    assert (record["pii_category"], record["data_domain"], record["data_subject"], record["review_status"]) == (
        category,
        domain,
        subject,
        status,
    )


def test_names_tax_codes_and_ibans_are_direct_pii(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, indexed = registry
    name_keys = {
        "crm.clienti.nome",
        "crm.clienti.cognome",
        "hr.dipendenti.nome",
        "hr.dipendenti.cognome",
        "crm.referenti_commerciali.nome_ref",
        "billing.coordinate_bancarie.intestatario",
        "hr.formazione.docente",
    }
    for key in name_keys:
        assert indexed[key]["pii_category"] == "PII-diretta"
        assert indexed[key]["data_domain"] == "person_name"
    for record in records:
        if record["data_domain"] in {"italian_iban", "italian_tax_code"} and record["pii_category"] != "PII-nascosta":
            assert record["pii_category"] == "PII-diretta"


def test_masking_rules_and_consistency_groups(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, indexed = registry
    assert all(record["masking_rule"] for record in records if record["pii_category"].startswith("PII-"))
    assert all(record["masking_rule"] == "preserve_value" for record in records if record["pii_category"] == "Non-PII")
    assert all(
        record["masking_rule"] == "review_before_masking" for record in records if record["pii_category"] == "Dubbio"
    )
    expected_groups = {
        "crm.clienti.cod_fisc": "customer_tax_code",
        "billing.sconti.cod_rif": "customer_tax_code",
        "hr.dipendenti.cod_fisc": "employee_tax_code",
        "crm.clienti.email": "customer_email",
        "hr.dipendenti.email_aziendale": "employee_email",
        "hr.dipendenti.iban": "employee_iban",
        "hr.buste_paga.iban_accredito": "employee_iban",
        "billing.coordinate_bancarie.iban": "customer_iban",
        "crm.referenti_commerciali.email_ref": "commercial_contact_email",
        "crm.referenti_commerciali.telefono_ref": "commercial_contact_phone",
    }
    for key, group in expected_groups.items():
        assert indexed[key]["consistency_group"] == group


def test_suspected_relationships_are_not_promoted(registry: tuple[list[dict], dict[str, dict]]) -> None:
    _, indexed = registry
    for key in ("billing.coordinate_bancarie.cliente_id", "billing.sconti.cliente_id"):
        statuses = {item["status"] for item in indexed[key]["logical_relationship"]}
        assert statuses == {"logical_suspected"}


def test_catalog_contains_one_row_per_registry_record(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, _ = registry
    with Path("output/pii_catalog.csv").open(encoding="utf-8", newline="") as input_file:
        catalog = list(csv.DictReader(input_file))
    assert len(catalog) == len(records) == 109


def test_outputs_are_deterministic(registry: tuple[list[dict], dict[str, dict]]) -> None:
    paths = (REGISTRY_PATH, Path("output/pii_catalog.csv"), Path("docs/CLASSIFICAZIONE_PII.md"))
    first = {path: path.read_bytes() for path in paths}
    generate_classification()
    second = {path: path.read_bytes() for path in paths}
    assert first == second


def test_markdown_is_generated_from_registry(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))["columns"]
    assert Path("docs/CLASSIFICAZIONE_PII.md").read_text(encoding="utf-8") == render_classification_markdown(records)
    assert len(records) == 109


def test_outputs_contain_no_complete_source_pii(registry: tuple[list[dict], dict[str, dict]]) -> None:
    output = REGISTRY_PATH.read_text(encoding="utf-8")
    output += Path("output/pii_catalog.csv").read_text(encoding="utf-8")
    output += Path("docs/CLASSIFICAZIONE_PII.md").read_text(encoding="utf-8")
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT email, telefono, cod_fisc FROM crm.clienti")
        sensitive = [str(value) for row in cursor.fetchall() for value in row if value]
        cursor.execute("SELECT iban FROM hr.dipendenti UNION ALL SELECT iban FROM billing.coordinate_bancarie")
        sensitive.extend(row[0] for row in cursor.fetchall())
        cursor.execute("SELECT testo FROM crm.note_cliente UNION ALL SELECT testo_sollecito FROM billing.solleciti")
        sensitive.extend(row[0] for row in cursor.fetchall())
    assert not any(value in output for value in sensitive)


def test_registry_rejects_missing_column(registry: tuple[list[dict], dict[str, dict]]) -> None:
    records, _ = registry
    domains = yaml.safe_load(DOMAINS_PATH.read_text(encoding="utf-8"))["domains"]
    expected = {(r["schema_name"], r["table_name"], r["column_name"]) for r in records}
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_registry(records[:-1], expected, domains)


def test_no_generic_markers_in_governance_outputs(registry: tuple[list[dict], dict[str, dict]]) -> None:
    paths = (
        DOMAINS_PATH,
        Path("config/classification_overrides.yml"),
        REGISTRY_PATH,
        Path("output/pii_catalog.csv"),
        Path("docs/CLASSIFICAZIONE_PII.md"),
    )
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    assert re.search(r"\b(?:todo|tbd|placeholder)\b|unknown_reason|to_be_defined", text) is None


def test_classification_does_not_modify_source_data(tmp_path: Path) -> None:
    def snapshot() -> str:
        data = {}
        with get_connection() as connection, connection.cursor() as cursor:
            for table, columns in TABLE_COLUMNS.items():
                cursor.execute(f"SELECT * FROM {table} ORDER BY {columns[0]}")
                data[table] = cursor.fetchall()
        return dataset_digest(data)

    before = snapshot()
    generate_classification()
    assert before == snapshot()


def test_module_command_runs_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.classify"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Registry generated for 109 columns" in result.stdout
