from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from src.db import get_connection
from src.inventory import (
    CONFIRMED_LOGICAL_RELATIONSHIPS,
    INVENTORY_FIELDS,
    RELATIONSHIP_FIELDS,
    generate_inventory,
)


@pytest.fixture(scope="module")
def generated_inventory(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, list[dict[str, str]], list[dict[str, str]]]:
    output_dir = tmp_path_factory.mktemp("inventory")
    generate_inventory(output_dir)
    with (output_dir / "inventory.csv").open(encoding="utf-8", newline="") as file:
        inventory = list(csv.DictReader(file))
    with (output_dir / "logical_relationships.csv").open(encoding="utf-8", newline="") as file:
        relationships = list(csv.DictReader(file))
    return output_dir, inventory, relationships


def test_exact_source_schemas_and_tables(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, inventory, _ = generated_inventory
    assert {row["schema_name"] for row in inventory} == {"billing", "crm", "hr"}
    assert len({(row["schema_name"], row["table_name"]) for row in inventory}) == 20
    assert not any(row["schema_name"].startswith("masked_") for row in inventory)


def test_one_inventory_row_per_database_column(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, inventory, _ = generated_inventory
    keys = [(row["schema_name"], row["table_name"], row["column_name"]) for row in inventory]
    assert len(keys) == len(set(keys))
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema IN ('crm', 'hr', 'billing')")
        assert len(inventory) == cursor.fetchone()[0]


def test_inventory_is_deterministically_sorted(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, inventory, _ = generated_inventory
    order = [(row["schema_name"], row["table_name"], int(row["ordinal_position"])) for row in inventory]
    assert order == sorted(order)
    assert tuple(inventory[0]) == INVENTORY_FIELDS


def test_catalog_constraints_are_represented(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, inventory, relationships = generated_inventory
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT contype, count(*) FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname IN ('crm', 'hr', 'billing') AND contype IN ('p', 'f', 'u', 'c')
            GROUP BY contype
        """)
        counts = dict(cursor.fetchall())
    assert sum(row["is_primary_key"] == "true" for row in inventory) >= counts["p"]
    assert sum(row["relationship_status"] == "declared" for row in relationships) == counts["f"]
    assert sum(row["is_unique"] == "true" for row in inventory) >= counts["u"]
    assert sum(bool(row["check_constraint"]) for row in inventory) >= counts["c"]


def test_composite_unique_constraint_is_stable_without_false_parent_uniqueness(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, inventory, relationships = generated_inventory
    payroll_members = {
        row["column_name"]
        for row in inventory
        if row["schema_name"] == "hr"
        and row["table_name"] == "buste_paga"
        and "uq_buste_paga_periodo" in row["constraint_name"]
    }
    assert payroll_members == {"dipendente_id", "mese", "anno"}
    assert not any(
        row["target_schema"] == "hr" and row["target_table"] == "buste_paga" and row["target_column"] in payroll_members
        for row in relationships
    )


def test_approved_logical_relationships_are_confirmed(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, _, relationships = generated_inventory
    indexed = {
        (
            row["source_schema"],
            row["source_table"],
            row["source_column"],
            row["target_schema"],
            row["target_table"],
            row["target_column"],
        ): row
        for row in relationships
    }
    for relationship in CONFIRMED_LOGICAL_RELATIONSHIPS:
        row = indexed[relationship]
        assert row["relationship_status"] == "logical_confirmed"
        assert row["orphan_count"] == "0"
        assert row["match_percentage"] == "100.00"


def test_inventory_does_not_create_foreign_keys(tmp_path: Path) -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT count(*) FROM information_schema.table_constraints
            WHERE constraint_type = 'FOREIGN KEY' AND table_schema IN ('crm', 'hr', 'billing')
        """)
        before = cursor.fetchone()[0]
    generate_inventory(tmp_path)
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT count(*) FROM information_schema.table_constraints
            WHERE constraint_type = 'FOREIGN KEY' AND table_schema IN ('crm', 'hr', 'billing')
        """)
        after = cursor.fetchone()[0]
    assert before == after


def test_csv_contains_no_source_pii(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    output_dir, _, _ = generated_inventory
    output_text = (output_dir / "inventory.csv").read_text(encoding="utf-8")
    output_text += (output_dir / "logical_relationships.csv").read_text(encoding="utf-8")
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT email, cod_fisc FROM crm.clienti LIMIT 10")
        pii_values = [value for row in cursor.fetchall() for value in row]
    assert not any(value in output_text for value in pii_values)


def test_outputs_are_byte_identical(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    output_dir, _, _ = generated_inventory
    first = {name: (output_dir / name).read_bytes() for name in ("inventory.csv", "logical_relationships.csv")}
    generate_inventory(output_dir)
    second = {name: (output_dir / name).read_bytes() for name in first}
    assert first == second


def test_relationship_schema_is_stable(
    generated_inventory: tuple[Path, list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _, _, relationships = generated_inventory
    assert relationships
    assert tuple(relationships[0]) == RELATIONSHIP_FIELDS
    assert {row["relationship_status"] for row in relationships} <= {
        "declared",
        "logical_confirmed",
        "logical_suspected",
        "not_confirmed",
    }


def test_module_command_runs_from_repository_root(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.inventory"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Inventory generated:" in result.stdout
