"""Deterministic generation and loading of an entirely synthetic dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from faker import Faker
from psycopg import sql

from src.infrastructure.database.connection import get_connection


DEFAULT_SEED = 20260804
REFERENCE_DATE = date(2025, 12, 31)

CF_ODD_VALUES = {
    **dict(zip("0123456789", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21))),
    **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23))),
}
CF_MONTH_CODES = "ABCDEHLMPRST"

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "crm.clienti": ("cliente_id", "nome", "cognome", "email", "telefono", "cod_fisc", "data_nascita", "segmento", "data_registrazione"),
    "crm.indirizzi": ("indirizzo_id", "cliente_id", "via", "cap", "citta", "provincia"),
    "crm.contatti_extra": ("contatto_id", "cliente_id", "tipo", "valore"),
    "crm.ordini": ("ordine_id", "cliente_id", "data_ordine", "importo", "stato"),
    "crm.note_cliente": ("nota_id", "cliente_id", "testo", "data_nota"),
    "crm.campagne": ("campagna_id", "nome_campagna", "email_template", "data_inizio"),
    "crm.consensi": ("consenso_id", "cliente_id", "tipo_consenso", "data_consenso", "revocato"),
    "crm.referenti_commerciali": ("referente_id", "nome_ref", "email_ref", "telefono_ref"),
    "hr.reparti": ("reparto_id", "nome_reparto", "responsabile_id"),
    "hr.dipendenti": ("dipendente_id", "nome", "cognome", "cod_fisc", "email_aziendale", "iban", "data_assunzione", "reparto_id"),
    "hr.buste_paga": ("busta_id", "dipendente_id", "mese", "anno", "lordo", "netto", "iban_accredito"),
    "hr.presenze": ("presenza_id", "dipendente_id", "data", "ore", "tipo"),
    "hr.valutazioni": ("valutazione_id", "dipendente_id", "valutatore_id", "anno", "punteggio", "commento"),
    "hr.formazione": ("corso_id", "titolo", "docente", "data_corso"),
    "billing.fatture": ("fattura_id", "cliente_id", "numero_fattura", "data_emissione", "importo", "iva", "stato"),
    "billing.pagamenti": ("pagamento_id", "fattura_id", "data_pagamento", "importo_pagato", "metodo", "riferimento_bancario", "rif_esterno"),
    "billing.coordinate_bancarie": ("coordinata_id", "cliente_id", "iban", "intestatario", "banca"),
    "billing.solleciti": ("sollecito_id", "fattura_id", "data_invio", "destinatario_email", "testo_sollecito"),
    "billing.sconti": ("sconto_id", "cliente_id", "codice_sconto", "percentuale", "data_scadenza", "cod_rif"),
    "billing.report_mensili": ("report_id", "mese", "anno", "totale_fatturato", "totale_incassato"),
}

PRIMARY_KEYS = {
    table: columns[0] for table, columns in TABLE_COLUMNS.items()
}


def tax_code_check_character(first_fifteen: str) -> str:
    """Return the official Italian tax-code check character."""
    if len(first_fifteen) != 15:
        raise ValueError("A tax-code payload must contain 15 characters")
    total = 0
    for position, character in enumerate(first_fifteen, start=1):
        if position % 2:
            total += CF_ODD_VALUES[character]
        else:
            total += int(character) if character.isdigit() else ord(character) - 65
    return chr(65 + total % 26)


def is_valid_tax_code(value: str) -> bool:
    if len(value) != 16 or not value.isalnum() or value != value.upper():
        return False
    try:
        return tax_code_check_character(value[:15]) == value[-1]
    except (KeyError, ValueError):
        return False


def synthetic_tax_code(rng: random.Random, used: set[str]) -> str:
    while True:
        prefix = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6))
        year = rng.randrange(0, 100)
        month = rng.choice(CF_MONTH_CODES)
        day = rng.randrange(1, 32) + rng.choice((0, 40))
        municipality = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + f"{rng.randrange(0, 1000):03d}"
        payload = f"{prefix}{year:02d}{month}{day:02d}{municipality}"
        value = payload + tax_code_check_character(payload)
        if value not in used:
            used.add(value)
            return value


def _iban_mod97(value: str) -> int:
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value)
    remainder = 0
    for character in numeric:
        remainder = (remainder * 10 + int(character)) % 97
    return remainder


def synthetic_italian_iban(rng: random.Random, used: set[str]) -> str:
    while True:
        # ABI and CAB are deliberately zeroed: checksum-valid, but not routable.
        bban = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ("0" * 10) + "".join(
            str(rng.randrange(10)) for _ in range(12)
        )
        check_digits = 98 - _iban_mod97(bban + "IT00")
        value = f"IT{check_digits:02d}{bban}"
        if value not in used:
            used.add(value)
            return value


def is_valid_italian_iban(value: str) -> bool:
    return (
        len(value) == 27
        and value.startswith("IT")
        and value[2:].isalnum()
        and _iban_mod97(value[4:] + value[:4]) == 1
    )


def _money(rng: random.Random, minimum: int, maximum: int) -> Decimal:
    return Decimal(rng.randrange(minimum * 100, maximum * 100 + 1)) / 100


def _phone(index: int) -> str:
    return f"+39 000 {index:07d}"


def build_dataset(seed: int) -> dict[str, list[tuple[Any, ...]]]:
    """Build all rows without touching the database."""
    rng = random.Random(seed)
    fake = Faker("it_IT")
    fake.seed_instance(seed)
    rows = {table: [] for table in TABLE_COLUMNS}
    used_tax_codes: set[str] = set()
    used_ibans: set[str] = set()

    customers: list[dict[str, Any]] = []
    for customer_id in range(1, 151):
        first_name = fake.first_name()
        last_name = fake.last_name()
        email = f"cliente{customer_id:03d}@example.test"
        tax_code = synthetic_tax_code(rng, used_tax_codes)
        birth_date = date(rng.randrange(1945, 2005), rng.randrange(1, 13), rng.randrange(1, 28))
        customer = {
            "id": customer_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": _phone(customer_id),
            "tax_code": tax_code,
            "birth_date": birth_date,
        }
        customers.append(customer)
        rows["crm.clienti"].append((
            customer_id, first_name, last_name, email, customer["phone"], tax_code,
            birth_date, ("retail", "premium", "business")[customer_id % 3],
            datetime(2021, 1, 1) + timedelta(days=rng.randrange(0, 1825), minutes=customer_id),
        ))
        rows["crm.indirizzi"].append((
            customer_id, customer_id, f"Via Sintetica {customer_id}", f"{10000 + customer_id:05d}",
            f"Citta Test {customer_id % 20:02d}", f"P{customer_id % 100:02d}",
        ))
        rows["crm.contatti_extra"].append((customer_id, customer_id, "email", email))
        if customer_id <= 50:
            rows["crm.contatti_extra"].append((150 + customer_id, customer_id, "telefono", customer["phone"]))

    for order_id in range(1, 301):
        customer = customers[(order_id * 17 - 1) % len(customers)]
        rows["crm.ordini"].append((
            order_id, customer["id"], REFERENCE_DATE - timedelta(days=rng.randrange(1, 730)),
            _money(rng, 10, 1500), ("inserito", "spedito", "completato", "annullato")[order_id % 4],
        ))

    for note_id in range(1, 21):
        customer = customers[note_id - 1]
        rows["crm.note_cliente"].append((
            note_id, customer["id"],
            f"Contattare {customer['first_name']} {customer['last_name']} via {customer['email']} o {customer['phone']}.",
            datetime(2025, 1, 1) + timedelta(days=note_id),
        ))

    templates = (
        "Gentile {{nome}}, contattaci a supporto@{{dominio}}",
        "Offerta per {{nome}}: scrivi a vendite@{{dominio}}",
        "Ciao {{nome}}, assistenza disponibile a help@{{dominio}}",
        "Aggiornamento {{campagna}} da news@{{dominio}}",
        "Promemoria per {{nome}}: privacy@{{dominio}}",
    )
    for campaign_id, template in enumerate(templates, start=1):
        rows["crm.campagne"].append((campaign_id, f"Campagna sintetica {campaign_id}", template, date(2025, campaign_id, 1)))

    for consent_id in range(1, 201):
        rows["crm.consensi"].append((
            consent_id, (consent_id - 1) % 150 + 1,
            ("marketing", "profilazione", "terze_parti")[consent_id % 3],
            datetime(2024, 1, 1) + timedelta(days=consent_id), consent_id % 11 == 0,
        ))

    for contact_id in range(1, 31):
        rows["crm.referenti_commerciali"].append((
            contact_id, fake.name(), f"referente{contact_id:03d}@example.test", _phone(5000 + contact_id),
        ))

    departments = ("Ingegneria", "Amministrazione", "Risorse Umane", "Vendite", "Operazioni", "Qualita")
    for department_id, name in enumerate(departments, start=1):
        rows["hr.reparti"].append((department_id, name, department_id))

    employees: list[dict[str, Any]] = []
    for employee_id in range(1, 51):
        first_name = fake.first_name()
        last_name = fake.last_name()
        iban = synthetic_italian_iban(rng, used_ibans)
        employee = {
            "id": employee_id,
            "first_name": first_name,
            "last_name": last_name,
            "tax_code": synthetic_tax_code(rng, used_tax_codes),
            "email": f"dipendente{employee_id:03d}@example.test",
            "iban": iban,
        }
        employees.append(employee)
        rows["hr.dipendenti"].append((
            employee_id, first_name, last_name, employee["tax_code"], employee["email"], iban,
            date(2015, 1, 1) + timedelta(days=rng.randrange(0, 3650)), (employee_id - 1) % 6 + 1,
        ))
        for offset, month in enumerate((11, 12)):
            gross = _money(rng, 2200, 6500)
            rows["hr.buste_paga"].append((
                (employee_id - 1) * 2 + offset + 1, employee_id, month, 2025,
                gross, (gross * Decimal("0.72")).quantize(Decimal("0.01")), iban,
            ))
        for day_offset in range(5):
            presence_id = (employee_id - 1) * 5 + day_offset + 1
            rows["hr.presenze"].append((
                presence_id, employee_id, date(2025, 12, 1) + timedelta(days=day_offset),
                Decimal("8.00"), "presenza",
            ))

    for evaluation_id in range(1, 31):
        employee = employees[evaluation_id - 1]
        evaluator = employees[(evaluation_id + 4) % 50]
        comment = f"Valutazione sintetica positiva, punteggio {6 + evaluation_id % 5}."
        if evaluation_id <= 10:
            comment = f"{employee['first_name']} {employee['last_name']} puo essere contattato a {employee['email']}."
        rows["hr.valutazioni"].append((
            evaluation_id, employee["id"], evaluator["id"], 2025,
            Decimal(6 + evaluation_id % 5), comment,
        ))

    for course_id in range(1, 11):
        rows["hr.formazione"].append((
            course_id, f"Corso sintetico {course_id}", fake.name(),
            date(2025, (course_id - 1) % 12 + 1, 15),
        ))

    invoices: list[dict[str, Any]] = []
    for invoice_id in range(1, 201):
        customer = customers[(invoice_id * 13 - 1) % 150]
        amount = _money(rng, 25, 2500)
        invoice = {"id": invoice_id, "customer": customer, "amount": amount}
        invoices.append(invoice)
        rows["billing.fatture"].append((
            invoice_id, customer["id"], f"FT-SYN-2025-{invoice_id:05d}",
            date(2025, 1, 1) + timedelta(days=(invoice_id * 7) % 350), amount,
            Decimal("22.00"), ("emessa", "pagata", "scaduta")[invoice_id % 3],
        ))

    for payment_id, invoice in enumerate(invoices[:160], start=1):
        customer = invoice["customer"]
        bank_reference = customer["tax_code"] if payment_id % 4 == 0 else f"SYNREF{payment_id:08d}"
        rows["billing.pagamenti"].append((
            payment_id, invoice["id"], date(2025, 1, 2) + timedelta(days=(payment_id * 7) % 350),
            invoice["amount"], ("bonifico", "carta", "addebito")[payment_id % 3],
            bank_reference, customer["email"],
        ))

    for coordinate_id, customer in enumerate(customers[:90], start=1):
        rows["billing.coordinate_bancarie"].append((
            coordinate_id, customer["id"], synthetic_italian_iban(rng, used_ibans),
            f"{customer['first_name']} {customer['last_name']}", f"Banca Sintetica {coordinate_id % 7}",
        ))

    for reminder_id, invoice in enumerate(invoices[160:], start=1):
        customer = invoice["customer"]
        rows["billing.solleciti"].append((
            reminder_id, invoice["id"], date(2025, 12, 1) + timedelta(days=reminder_id % 28),
            customer["email"],
            f"Sollecito sintetico per {customer['first_name']} {customer['last_name']}; contatto {customer['email']}, CF {customer['tax_code']}.",
        ))

    for discount_id, customer in enumerate(customers[:60], start=1):
        rows["billing.sconti"].append((
            discount_id, customer["id"], f"SCONTO-SYN-{discount_id:04d}",
            Decimal(5 + discount_id % 21), REFERENCE_DATE + timedelta(days=discount_id),
            customer["tax_code"],
        ))

    for month in range(1, 13):
        rows["billing.report_mensili"].append((
            month, month, 2025, Decimal(100000 + month * 1250), Decimal(90000 + month * 1100),
        ))

    return rows


def dataset_digest(rows: dict[str, list[tuple[Any, ...]]]) -> str:
    canonical = json.dumps(rows, default=str, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _qualified_identifier(table: str) -> sql.Composed:
    schema, name = table.split(".")
    return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))


def _insert_rows(cursor: Any, table: str, columns: Iterable[str], values: list[tuple[Any, ...]]) -> None:
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        _qualified_identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    cursor.executemany(query, values)


def load_dataset(seed: int = DEFAULT_SEED) -> dict[str, int]:
    rows = build_dataset(seed)
    table_list = sql.SQL(", ").join(_qualified_identifier(table) for table in TABLE_COLUMNS)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(table_list))
            for table, columns in TABLE_COLUMNS.items():
                _insert_rows(cursor, table, columns, rows[table])
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), %s, true)",
                    (table, PRIMARY_KEYS[table], len(rows[table])),
                )
    return {table: len(values) for table, values in rows.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic test data")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Explicit deterministic seed")
    args = parser.parse_args()
    counts = load_dataset(args.seed)
    print(f"Synthetic dataset loaded with seed {args.seed} ({sum(counts.values())} rows).")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
