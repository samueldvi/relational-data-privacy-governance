from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.db import get_connection
from src.generate_data import (
    DEFAULT_SEED,
    TABLE_COLUMNS,
    build_dataset,
    dataset_digest,
    is_valid_italian_iban,
    is_valid_tax_code,
    load_dataset,
)


@pytest.fixture(scope="session", autouse=True)
def generated_database() -> None:
    load_dataset(DEFAULT_SEED)


def fetch_one(query: str) -> int:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
        assert row is not None
        return row[0]


def database_digest() -> str:
    snapshot = {}
    with get_connection() as connection, connection.cursor() as cursor:
        for table, columns in TABLE_COLUMNS.items():
            cursor.execute(f"SELECT * FROM {table} ORDER BY {columns[0]}")
            snapshot[table] = cursor.fetchall()
    return dataset_digest(snapshot)


def test_expected_volumes_and_every_table_is_populated() -> None:
    minimums = {"crm.clienti": 150, "hr.dipendenti": 50, "crm.referenti_commerciali": 30}
    with get_connection() as connection, connection.cursor() as cursor:
        for table in TABLE_COLUMNS:
            cursor.execute(f"SELECT count(*) FROM {table}")
            count = cursor.fetchone()[0]
            assert count > 0, table
            assert count >= minimums.get(table, 1), table


def test_tax_codes_are_formally_valid_and_unique() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT cod_fisc FROM crm.clienti UNION ALL SELECT cod_fisc FROM hr.dipendenti")
        values = [row[0] for row in cursor.fetchall()]
    assert len(values) >= 5
    assert len(values) == len(set(values))
    assert all(is_valid_tax_code(value) for value in values)


def test_ibans_are_formally_valid_and_unique_where_constrained() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT iban FROM hr.dipendenti UNION ALL SELECT iban FROM billing.coordinate_bancarie")
        values = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT count(*) = count(DISTINCT iban) FROM billing.coordinate_bancarie")
        unique_ok = cursor.fetchone()[0]
    assert len(values) >= 3
    assert all(is_valid_italian_iban(value) for value in values)
    assert unique_ok


def test_declared_foreign_keys_have_no_orphans() -> None:
    assert fetch_one("""
        SELECT count(*) FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY' AND table_schema IN ('crm', 'hr', 'billing')
    """) == 12
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_logical_relationships_are_coherent() -> None:
    assert fetch_one("SELECT count(*) FROM billing.fatture f LEFT JOIN crm.clienti c USING (cliente_id) WHERE c.cliente_id IS NULL") == 0
    assert fetch_one("SELECT count(*) FROM hr.reparti r LEFT JOIN hr.dipendenti d ON d.dipendente_id = r.responsabile_id WHERE d.dipendente_id IS NULL") == 0


def test_payroll_iban_matches_employee_iban() -> None:
    assert fetch_one("""
        SELECT count(*) FROM hr.buste_paga b
        JOIN hr.dipendenti d USING (dipendente_id)
        WHERE b.iban_accredito <> d.iban
    """) == 0


def test_free_text_contains_expected_synthetic_pii() -> None:
    assert fetch_one("SELECT count(*) FROM crm.note_cliente WHERE testo ~ '@example\\.test' ") >= 10
    assert fetch_one("SELECT count(*) FROM hr.valutazioni WHERE commento ~ '@example\\.test' ") >= 10
    assert fetch_one("SELECT count(*) FROM billing.solleciti WHERE testo_sollecito ~ '@example\\.test' ") > 0


def test_false_positive_templates_use_placeholders() -> None:
    assert fetch_one("SELECT count(*) FROM crm.campagne WHERE email_template LIKE '%@{{dominio}}%'") == 5


def test_trap_columns_exist_and_match_source_values() -> None:
    assert fetch_one("""
        SELECT count(*) FROM information_schema.columns
        WHERE (table_schema, table_name, column_name) IN (
            ('billing', 'sconti', 'cod_rif'), ('billing', 'pagamenti', 'rif_esterno')
        )
    """) == 2
    assert fetch_one("SELECT count(*) FROM billing.sconti s LEFT JOIN crm.clienti c ON c.cod_fisc = s.cod_rif WHERE c.cliente_id IS NULL") == 0
    assert fetch_one("SELECT count(*) FROM billing.pagamenti p LEFT JOIN crm.clienti c ON lower(c.email) = lower(p.rif_esterno) WHERE c.cliente_id IS NULL") == 0


def test_all_unique_constraints_hold() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        for query in (
            "SELECT count(*) - count(DISTINCT cod_fisc) FROM crm.clienti",
            "SELECT count(*) - count(DISTINCT cod_fisc) FROM hr.dipendenti",
            "SELECT count(*) - count(DISTINCT email_aziendale) FROM hr.dipendenti",
            "SELECT count(*) - count(DISTINCT iban) FROM billing.coordinate_bancarie",
            "SELECT count(*) - count(DISTINCT numero_fattura) FROM billing.fatture",
            "SELECT count(*) - count(DISTINCT codice_sconto) FROM billing.sconti",
        ):
            cursor.execute(query)
            assert cursor.fetchone()[0] == 0


def test_same_seed_is_deterministic_and_other_seed_varies() -> None:
    first = dataset_digest(build_dataset(DEFAULT_SEED))
    second = dataset_digest(build_dataset(DEFAULT_SEED))
    different = dataset_digest(build_dataset(DEFAULT_SEED + 1))
    assert first == second
    assert first != different


def test_reset_and_reload_is_idempotent() -> None:
    first_counts = load_dataset(DEFAULT_SEED)
    first_digest = database_digest()
    second_counts = load_dataset(DEFAULT_SEED)
    second_digest = database_digest()
    try:
        load_dataset(DEFAULT_SEED + 1)
        different_digest = database_digest()
    finally:
        load_dataset(DEFAULT_SEED)
    assert first_counts == second_counts
    assert first_digest == second_digest
    assert first_digest != different_digest


def test_no_credentials_or_public_email_domains_are_hardcoded() -> None:
    source = Path("src/generate_data.py").read_text(encoding="utf-8")
    forbidden = ("POSTGRES_PASSWORD=", "gmail.com", "yahoo.com", "hotmail.com", "@outlook.")
    assert not any(value.lower() in source.lower() for value in forbidden)
    domains = re.findall(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+)", source)
    assert set(domains) <= {"example.test"}
