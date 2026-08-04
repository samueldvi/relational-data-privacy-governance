from __future__ import annotations

import json
import os
import re
import secrets

import pytest

from src.apply_masking import MANIFEST_PATH, apply_masking, redact_bank_reference, validate_only
from src.db import get_connection


@pytest.fixture(scope="module", autouse=True)
def loaded_masked_database() -> None:
    original_secret = os.environ["MASKING_SECRET"]
    os.environ["MASKING_SECRET"] = secrets.token_urlsafe(48)
    try:
        apply_masking()
        yield
    finally:
        os.environ["MASKING_SECRET"] = original_secret
        apply_masking()


def test_all_tables_rows_constraints_and_relationships_validate() -> None:
    result = validate_only()
    assert len(result["masked_counts"]) == 20
    assert sum(result["masked_counts"].values()) == 2063
    assert result["source_counts"] == result["masked_counts"]
    assert len(result["table_checksums"]) == 20


def test_technical_keys_are_identical_and_masked_sequences_are_owned_locally() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM crm.clienti source
            FULL JOIN masked_crm.clienti masked USING (cliente_id)
            WHERE source.cliente_id IS NULL OR masked.cliente_id IS NULL
            """
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_schema LIKE 'masked\\_%' ESCAPE '\\'
              AND column_default LIKE 'nextval(%'
              AND column_default NOT LIKE '%masked_%'
            """
        )
        assert cursor.fetchone()[0] == 0


def test_required_cross_table_consistency_and_subject_separation() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM billing.sconti source_sconto
            JOIN crm.clienti source_cliente ON source_cliente.cod_fisc=source_sconto.cod_rif
            JOIN masked_billing.sconti masked_sconto
              ON masked_sconto.sconto_id=source_sconto.sconto_id
            JOIN masked_crm.clienti masked_cliente
              ON masked_cliente.cliente_id=source_cliente.cliente_id
            WHERE masked_sconto.cod_rif <> masked_cliente.cod_fisc
            """
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            """
            SELECT count(*) FROM hr.buste_paga source_busta
            JOIN hr.dipendenti source_dipendente
              ON source_dipendente.dipendente_id=source_busta.dipendente_id
             AND source_dipendente.iban=source_busta.iban_accredito
            JOIN masked_hr.buste_paga masked_busta
              ON masked_busta.busta_id=source_busta.busta_id
            JOIN masked_hr.dipendenti masked_dipendente
              ON masked_dipendente.dipendente_id=source_dipendente.dipendente_id
            WHERE masked_busta.iban_accredito <> masked_dipendente.iban
            """
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            """
            SELECT count(*) FROM masked_crm.clienti customer
            JOIN masked_hr.dipendenti employee
              ON customer.cod_fisc=employee.cod_fisc
            """
        )
        assert cursor.fetchone()[0] == 0


def test_conditional_contact_masking_uses_safe_formats() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT tipo, valore FROM masked_crm.contatti_extra ORDER BY contatto_id")
        for contact_type, value in cursor.fetchall():
            if contact_type in {"email", "pec"}:
                assert value.endswith("@example.test")
            elif contact_type == "telefono":
                assert value.startswith("+39 000 ")
            else:
                pytest.fail(f"Unsupported contact type in fixture: {contact_type}")


def test_approved_bank_reference_redaction_is_idempotent_and_complete_for_known_patterns() -> None:
    examples = (
        "CF RSSMRA80A01H501U",
        "IBAN IT60X0542811101000000123456",
        "email mario.rossi@example.com",
        "tel +39 347 1234567",
        "carta 1234 **** **** 9876",
        "TRN TRNABC123456789",
    )
    for example in examples:
        redacted = redact_bank_reference(example)
        assert redacted != example
        assert redact_bank_reference(redacted) == redacted
        assert "[REDACTED_" in redacted
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT riferimento_bancario FROM masked_billing.pagamenti ORDER BY pagamento_id")
        values = [value for (value,) in cursor.fetchall() if value]
    assert values
    assert all("[REDACTED_" in value for value in values)
    assert not any(re.search(r"\bIT\d{2}[A-Z0-9]{23}\b", value) for value in values)


def test_manifest_reports_only_aggregate_metadata_and_checksums() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["final_status"] == "success"
    assert manifest["tables_processed"] == 20
    assert manifest["source_rows_by_table"] == manifest["masked_rows_by_table"]
    assert manifest["collision_statistics"]["collisions_resolved"] >= 0
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["global_checksum"])
    serialized = json.dumps(manifest, sort_keys=True)
    assert "MASKING_SECRET" not in serialized
    assert "riferimento_bancario" not in serialized or "billing.pagamenti.riferimento_bancario" in serialized
