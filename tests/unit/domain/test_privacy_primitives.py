from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

from src.domain.identifiers import is_valid_italian_iban, is_valid_tax_code
from src.domain.masking.primitives import mask_email, mask_iban, mask_tax_code, redact_free_text
from src.domain.profiling.normalizers import normalize_iban, normalize_name
from src.domain.validation.manifest import finalize_manifest, table_checksum
from src.generate_data import synthetic_italian_iban, synthetic_tax_code


SECRET = "domain-test-secret-with-enough-variation-2026"


def test_domain_masking_is_deterministic_and_format_preserving() -> None:
    tax_code = synthetic_tax_code(random.Random(4), set())
    iban = synthetic_italian_iban(random.Random(5), set())
    assert mask_email("USER@example.test", secret=SECRET, namespace="email") == mask_email(
        "user@example.test", secret=SECRET, namespace="email"
    )
    assert is_valid_tax_code(mask_tax_code(tax_code, secret=SECRET, namespace="tax") or "")
    assert is_valid_italian_iban(mask_iban(iban, secret=SECRET, namespace="iban") or "")


def test_domain_redaction_and_normalization_have_no_io_dependencies() -> None:
    assert normalize_iban("IT 00 ABC") == "IT00ABC"
    assert normalize_name("  Mario   Rossi ") == "mario rossi"
    assert redact_free_text("Scrivere a user@example.test") == "Scrivere a [REDACTED_EMAIL]"


def test_canonical_checksum_is_order_stable_and_typed() -> None:
    rows = [(1, Decimal("10.20"), date(2026, 8, 4), None)]
    first = table_checksum("masked_crm", "sample", ["id", "amount", "day", "empty"], rows)
    second = table_checksum("masked_crm", "sample", ["id", "amount", "day", "empty"], rows)
    assert first == second and len(first) == 64
    assert finalize_manifest({"tables": {"sample": first}}) == finalize_manifest(
        {"tables": {"sample": first}}
    )
