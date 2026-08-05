from __future__ import annotations

import random
import secrets
from datetime import date
from pathlib import Path

import pytest
import yaml

from src.generate_data import (
    is_valid_italian_iban,
    is_valid_tax_code,
    synthetic_italian_iban,
    synthetic_tax_code,
)
from src.masking import (
    CONSISTENCY_GROUPS_PATH,
    DOCUMENTATION_PATH,
    MASKING_RULES_PATH,
    REGISTRY_PATH,
    InvalidConfigurationError,
    MissingSecretError,
    ReviewRequiredError,
    UnresolvableCollisionError,
    UnsupportedFormatError,
    WeakSecretError,
    get_masking_secret,
    mask_contact_value,
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
    render_masking_documentation,
    resolve_collisions,
    review_before_masking,
    shift_birth_date,
    validate_masking_configuration,
    validate_secret,
    write_masking_documentation,
)


@pytest.fixture()
def secret() -> str:
    return secrets.token_urlsafe(48)


@pytest.fixture()
def other_secret() -> str:
    return secrets.token_urlsafe(48)


@pytest.fixture()
def tax_code() -> str:
    return synthetic_tax_code(random.Random(101), set())


@pytest.fixture()
def iban() -> str:
    return synthetic_italian_iban(random.Random(202), set())


def test_secret_is_required_and_weak_secret_is_rejected_without_disclosure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MASKING_SECRET", raising=False)
    with pytest.raises(MissingSecretError, match="MASKING_SECRET"):
        get_masking_secret()
    weak = "short-secret-material"
    with pytest.raises(WeakSecretError) as error:
        validate_secret(weak)
    assert weak not in str(error.value)


def test_same_secret_is_deterministic_and_different_secret_changes_output(secret: str, other_secret: str) -> None:
    first = mask_email("utente@example.test", secret=secret, namespace="email.customer.v1")
    second = mask_email("utente@example.test", secret=secret, namespace="email.customer.v1")
    changed = mask_email("utente@example.test", secret=other_secret, namespace="email.customer.v1")
    assert first == second
    assert first != changed


def test_normalizations_are_explicit_and_case_insensitive(tax_code: str, iban: str) -> None:
    assert normalize_email("  UTENTE@EXAMPLE.TEST ") == "utente@example.test"
    assert normalize_tax_code(" ".join((tax_code[:8], tax_code[8:]))) == tax_code
    assert normalize_iban(" ".join((iban[:4], iban[4:]))) == iban
    assert normalize_phone("0039 000-1234567") == "+390001234567"
    assert normalize_name("  Persona   Sintetica ") == "persona sintetica"


@pytest.mark.parametrize(
    "function,kwargs",
    [
        (mask_email, {"namespace": "email.customer.v1"}),
        (mask_phone, {"namespace": "phone.customer.v1"}),
        (mask_tax_code, {"namespace": "tax.customer.v1"}),
        (mask_iban, {"namespace": "iban.customer.v1"}),
        (mask_person_name, {"namespace": "name.customer.v1"}),
        (mask_postal_address, {"namespace": "address.customer.v1"}),
    ],
)
def test_none_is_preserved(function, kwargs: dict[str, str], secret: str) -> None:
    assert function(None, secret=secret, **kwargs) is None
    assert function("", secret=secret, **kwargs) == ""


def test_email_output_is_valid_non_routable_and_normalized(secret: str) -> None:
    first = mask_email("  UTENTE@EXAMPLE.TEST ", secret=secret, namespace="email.customer.v1")
    second = mask_email("utente@example.test", secret=secret, namespace="email.customer.v1")
    assert first == second
    assert first is not None and first.startswith("u_") and first.endswith("@example.test")
    assert first.count("@") == 1


def test_phone_output_is_stable_and_synthetic(secret: str) -> None:
    first = mask_phone("+39 000 1234567", secret=secret, namespace="phone.customer.v1")
    second = mask_phone("0039-000-1234567", secret=secret, namespace="phone.customer.v1")
    assert first == second
    assert first is not None and first.startswith("+39 000 ") and len(first.split()[-1]) == 7


def test_tax_code_output_is_valid_and_consistent_across_trap_columns(secret: str, tax_code: str) -> None:
    customer_namespace = "tax_code.customer.v1"
    crm_value = mask_tax_code(tax_code, secret=secret, namespace=customer_namespace)
    billing_value = mask_tax_code(tax_code.lower(), secret=secret, namespace=customer_namespace)
    employee_value = mask_tax_code(tax_code, secret=secret, namespace="tax_code.employee.v1")
    assert crm_value == billing_value
    assert crm_value is not None and len(crm_value) == 16 and crm_value.isalnum()
    assert is_valid_tax_code(crm_value)
    assert employee_value != crm_value


def test_iban_output_is_valid_non_routable_and_consistent(secret: str, iban: str) -> None:
    first = mask_iban(iban, secret=secret, namespace="iban.employee.v1")
    second = mask_iban(" ".join((iban[:8], iban[8:])), secret=secret, namespace="iban.employee.v1")
    assert first == second
    assert first is not None and first.startswith("IT") and len(first) == 27
    assert first[5:15] == "0000000000"
    assert is_valid_italian_iban(first)


def test_person_name_preserves_token_count_without_global_state(secret: str, other_secret: str) -> None:
    first = mask_person_name("Persona  Sintetica", secret=secret, namespace="name.customer.v1")
    repeated = mask_person_name("persona sintetica", secret=secret, namespace="name.customer.v1")
    changed_secret = mask_person_name("Persona Sintetica", secret=other_secret, namespace="name.customer.v1")
    external = mask_person_name("Persona Sintetica", secret=secret, namespace="name.external.v1")
    assert first == repeated
    assert first is not None and len(first.split()) == 2
    assert changed_secret != first
    assert external != first


def test_birth_date_shift_is_bounded_deterministic_and_not_future(secret: str) -> None:
    original = date(2000, 2, 29)
    reference = date(2026, 8, 4)
    first = shift_birth_date(original, secret=secret, namespace="birth.customer.v1", reference_date=reference)
    second = shift_birth_date(original, secret=secret, namespace="birth.customer.v1", reference_date=reference)
    assert first == second
    assert first is not None and abs((first - original).days) <= 30
    assert first <= reference
    with pytest.raises(UnsupportedFormatError):
        shift_birth_date(date(2027, 1, 1), secret=secret, namespace="birth.customer.v1", reference_date=reference)


def test_free_text_redaction_handles_multiple_patterns_and_known_names(
    tax_code: str, iban: str, caplog: pytest.LogCaptureFixture
) -> None:
    text = f"Persona Sintetica: utente@example.test, +39 000 1234567, codice {tax_code}, conto {iban}."
    redacted = redact_free_text(text, known_names=["Persona Sintetica"])
    assert redacted is not None
    for marker in (
        "[REDACTED_EMAIL]",
        "[REDACTED_PHONE]",
        "[REDACTED_TAX_CODE]",
        "[REDACTED_IBAN]",
        "[REDACTED_NAME]",
    ):
        assert marker in redacted
    assert "codice" in redacted and "conto" in redacted
    assert text not in caplog.text


def test_contact_value_dispatch_and_postal_address(secret: str) -> None:
    email = mask_contact_value("utente@example.test", "email", secret=secret, namespace="contact.customer.v1")
    phone = mask_contact_value("+39 000 1234567", "telefono", secret=secret, namespace="contact.customer.v1")
    address = mask_postal_address("Via Sintetica 1", secret=secret, namespace="address.customer.v1")
    assert email is not None and email.endswith("@example.test")
    assert phone is not None and phone.startswith("+39 000 ")
    assert address is not None and address.startswith("Indirizzo sintetico ")
    with pytest.raises(UnsupportedFormatError):
        mask_contact_value("value", "unsupported", secret=secret, namespace="contact.customer.v1")


def test_collision_resolution_is_deterministic_and_order_independent() -> None:
    def candidate(value: str, counter: int) -> str:
        return "same" if counter == 0 else f"{value}-{counter}"

    first = resolve_collisions(["Beta", "alpha", "ALPHA"], normalizer=str.lower, candidate_generator=candidate)
    second = resolve_collisions(["ALPHA", "alpha", "Beta"], normalizer=str.lower, candidate_generator=candidate)
    assert first == second
    assert first.statistics.values_processed == 2
    assert first.statistics.collisions_detected == 1
    assert first.statistics.collisions_resolved == 1
    assert first.statistics.maximum_attempts == 2


def test_unresolvable_collision_raises_controlled_error() -> None:
    with pytest.raises(UnresolvableCollisionError):
        resolve_collisions(
            ["alpha", "beta"],
            normalizer=str.lower,
            candidate_generator=lambda _value, _counter: "same",
            max_attempts=2,
        )


def test_preservation_and_review_controls() -> None:
    approved = {"crm.clienti.cliente_id"}
    value = 1001
    assert preserve_technical_key(value, column="crm.clienti.cliente_id", approved_columns=approved) == value
    assert preserve_value(value) == value
    with pytest.raises(InvalidConfigurationError):
        preserve_technical_key(value, column="crm.clienti.nome", approved_columns=approved)
    with pytest.raises(ReviewRequiredError):
        review_before_masking("ambiguous", column="billing.pagamenti.riferimento_bancario")


def test_registry_rules_and_consistency_groups_are_fully_validated() -> None:
    summary = validate_masking_configuration()
    assert summary == {
        "registry_columns": 109,
        "masking_rules": 12,
        "consistency_groups": 9,
        "grouped_columns": 13,
    }
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))["columns"]
    rules = yaml.safe_load(MASKING_RULES_PATH.read_text(encoding="utf-8"))["rules"]
    groups = yaml.safe_load(CONSISTENCY_GROUPS_PATH.read_text(encoding="utf-8"))["groups"]
    assert {record["masking_rule"] for record in registry} <= set(rules)
    assert {record["consistency_group"] for record in registry if record["consistency_group"]} <= set(groups)


def test_masking_unit_module_has_no_database_dependency() -> None:
    source = Path("src/masking.py").read_text(encoding="utf-8")
    assert "src.db" not in source
    assert "psycopg" not in source
    assert "get_connection" not in source


def test_documentation_is_regenerable_and_deterministic(tmp_path: Path) -> None:
    first = render_masking_documentation()
    second = render_masking_documentation()
    assert first == second
    output = tmp_path / "rules.md"
    write_masking_documentation(output)
    assert output.read_text(encoding="utf-8") == first
    assert DOCUMENTATION_PATH.read_text(encoding="utf-8") == first


def test_no_secret_or_persistent_mapping_in_versioned_files(secret: str) -> None:
    paths = (
        MASKING_RULES_PATH,
        CONSISTENCY_GROUPS_PATH,
        DOCUMENTATION_PATH,
        Path("src/masking.py"),
    )
    content = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert secret not in content
    assert "MASKING_SECRET=" not in content
    assert not list(Path("config").glob("*mapping*"))
