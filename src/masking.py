"""Pure deterministic masking primitives and configuration validation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, TypeVar

from src.generate_data import is_valid_italian_iban, is_valid_tax_code, tax_code_check_character
from src.infrastructure.config.loader import load_yaml_path
from src.infrastructure.security.secret_provider import EnvironmentSecretProvider
from src.shared.errors import MaskingSecretError


MASKING_RULES_PATH = Path("config/masking_rules.yml")
CONSISTENCY_GROUPS_PATH = Path("config/consistency_groups.yml")
REGISTRY_PATH = Path("config/pii_registry.yml")
DOCUMENTATION_PATH = Path("docs/REGOLE_MASCHERAMENTO.md")
MINIMUM_SECRET_LENGTH = 32

EMAIL_PATTERN = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
EMAIL_IN_TEXT_PATTERN = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
TAX_CODE_IN_TEXT_PATTERN = re.compile(r"\b[A-Z0-9]{16}\b", re.IGNORECASE)
IBAN_IN_TEXT_PATTERN = re.compile(r"\bIT(?:\s?[0-9A-Z]){25}\b", re.IGNORECASE)
PHONE_IN_TEXT_PATTERN = re.compile(r"(?<!\w)(?:(?:\+|00)39)?(?:[\s().-]*\d){8,11}(?!\w)")

T = TypeVar("T")


class MaskingError(Exception):
    """Base exception for deterministic masking failures."""


class MissingSecretError(MaskingError):
    """Raised when MASKING_SECRET is unavailable."""


class WeakSecretError(MaskingError):
    """Raised when the provided secret fails minimum strength requirements."""


class InvalidConfigurationError(MaskingError):
    """Raised for registry or YAML configuration inconsistencies."""


class UnsupportedFormatError(MaskingError):
    """Raised when a value cannot be normalized or validated safely."""


class UnresolvableCollisionError(MaskingError):
    """Raised when deterministic retries cannot resolve a collision."""


class ReviewRequiredError(MaskingError):
    """Raised when a Dubbio column has no approved transformation."""


@dataclass(frozen=True)
class CollisionStatistics:
    values_processed: int
    collisions_detected: int
    collisions_resolved: int
    maximum_attempts: int


@dataclass(frozen=True)
class CollisionResolution:
    mapping: dict[str, str]
    statistics: CollisionStatistics


def validate_secret(secret: str | None) -> bytes:
    """Validate secret material without ever including it in error messages."""
    if secret is None or not secret:
        raise MissingSecretError("MASKING_SECRET is required for deterministic masking.")
    lowered = secret.lower()
    if (
        len(secret) < MINIMUM_SECRET_LENGTH
        or len(set(secret)) < 8
        or any(marker in lowered for marker in ("change_me", "replace_with", "example_secret"))
    ):
        raise WeakSecretError(
            f"MASKING_SECRET must contain at least {MINIMUM_SECRET_LENGTH} characters and sufficient variation."
        )
    return secret.encode("utf-8")


def get_masking_secret() -> str:
    try:
        secret = EnvironmentSecretProvider().masking_secret()
    except MaskingSecretError as error:
        raise MissingSecretError("MASKING_SECRET is required for deterministic masking.") from error
    validate_secret(secret)
    assert secret is not None
    return secret


def _digest(secret: str, namespace: str, normalized_value: str, counter: int = 0) -> bytes:
    key = validate_secret(secret)
    if not namespace.strip():
        raise InvalidConfigurationError("A non-empty masking namespace is required.")
    retry = f":retry:{counter}" if counter else ""
    message = f"{namespace}:{normalized_value}{retry}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).digest()


def _token(digest: bytes, length: int) -> str:
    return base64.b32encode(digest).decode("ascii").rstrip("=").lower()[:length]


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return ""
    if " " in normalized or not EMAIL_PATTERN.fullmatch(normalized):
        raise UnsupportedFormatError("Email value has an unsupported format.")
    return normalized


def normalize_tax_code(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).upper()
    if not normalized:
        return ""
    if not is_valid_tax_code(normalized):
        raise UnsupportedFormatError("Italian tax code must be 16 alphanumeric characters with a valid check character.")
    return normalized


def normalize_iban(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).upper()
    if not normalized:
        return ""
    if not is_valid_italian_iban(normalized):
        raise UnsupportedFormatError("Italian IBAN must have length 27 and a valid MOD-97 checksum.")
    return normalized


def normalize_phone(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    digits = re.sub(r"\D", "", stripped)
    if digits.startswith("0039"):
        digits = digits[4:]
    elif digits.startswith("39"):
        digits = digits[2:]
    if not 7 <= len(digits) <= 11:
        raise UnsupportedFormatError("Phone value has an unsupported international format.")
    return "+39" + digits


def normalize_name(value: str) -> str:
    normalized = " ".join(value.strip().split())
    return normalized.casefold()


def mask_email(
    value: str | None, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    if value is None:
        return None
    normalized = normalize_email(value)
    if not normalized:
        return ""
    return f"u_{_token(_digest(secret, namespace, normalized, counter), 20)}@example.test"


def mask_phone(
    value: str | None, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    if value is None:
        return None
    normalized = normalize_phone(value)
    if not normalized:
        return ""
    number = int.from_bytes(_digest(secret, namespace, normalized, counter)[:8], "big") % 10_000_000
    return f"+39 000 {number:07d}"


def mask_tax_code(
    value: str | None, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    if value is None:
        return None
    normalized = normalize_tax_code(value)
    if not normalized:
        return ""
    digest = _digest(secret, namespace, normalized, counter)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    month_codes = "ABCDEHLMPRST"
    prefix = "".join(letters[digest[index] % 26] for index in range(6))
    year = int.from_bytes(digest[6:8], "big") % 100
    month = month_codes[digest[8] % len(month_codes)]
    day = digest[9] % 31 + 1 + (40 if digest[10] % 2 else 0)
    municipality = letters[digest[11] % 26] + f"{int.from_bytes(digest[12:14], 'big') % 1000:03d}"
    body = f"{prefix}{year:02d}{month}{day:02d}{municipality}"
    return body + tax_code_check_character(body)


def _iban_mod97(value: str) -> int:
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value)
    remainder = 0
    for character in numeric:
        remainder = (remainder * 10 + int(character)) % 97
    return remainder


def mask_iban(
    value: str | None, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    if value is None:
        return None
    normalized = normalize_iban(value)
    if not normalized:
        return ""
    digest = _digest(secret, namespace, normalized, counter)
    cin = chr(65 + digest[0] % 26)
    account_number = int.from_bytes(digest[1:9], "big") % 1_000_000_000_000
    bban = f"{cin}0000000000{account_number:012d}"
    check_digits = 98 - _iban_mod97(bban + "IT00")
    return f"IT{check_digits:02d}{bban}"


def mask_person_name(
    value: str | None, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    if value is None:
        return None
    normalized = normalize_name(value)
    if not normalized:
        return ""
    tokens = normalized.split()
    output = []
    for index, _ in enumerate(tokens):
        digest = _digest(secret, namespace, f"{normalized}:token:{index}", counter)
        output.append(f"Persona_{_token(digest, 8)}")
    return " ".join(output)


def mask_postal_address(
    value: str | None, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    if value is None:
        return None
    normalized = normalize_name(value)
    if not normalized:
        return ""
    return f"Indirizzo sintetico {_token(_digest(secret, namespace, normalized, counter), 12)}"


def mask_contact_value(
    value: str | None, contact_type: str, *, secret: str, namespace: str, counter: int = 0
) -> str | None:
    normalized_type = contact_type.strip().lower()
    if normalized_type in {"email", "pec"}:
        return mask_email(value, secret=secret, namespace=f"{namespace}.email", counter=counter)
    if normalized_type in {"telefono", "phone"}:
        return mask_phone(value, secret=secret, namespace=f"{namespace}.phone", counter=counter)
    raise UnsupportedFormatError("Contact type is not supported by mask_contact_value.")


def shift_birth_date(
    value: date | None, *, secret: str, namespace: str, reference_date: date
) -> date | None:
    if value is None:
        return None
    if type(value) is not date:
        raise UnsupportedFormatError("Birth date must be a date value.")
    if value > reference_date:
        raise UnsupportedFormatError("Birth date cannot be after the explicit reference date.")
    raw_offset = int.from_bytes(_digest(secret, namespace, value.isoformat())[:2], "big") % 60
    offset = raw_offset - 30 if raw_offset < 30 else raw_offset - 29
    shifted = value + timedelta(days=offset)
    return min(shifted, reference_date)


def redact_free_text(text: str | None, *, known_names: Iterable[str] = ()) -> str | None:
    if text is None:
        return None
    if text == "":
        return ""
    redacted = EMAIL_IN_TEXT_PATTERN.sub("[REDACTED_EMAIL]", text)

    def redact_iban(match: re.Match[str]) -> str:
        candidate = re.sub(r"\s+", "", match.group(0)).upper()
        return "[REDACTED_IBAN]" if is_valid_italian_iban(candidate) else match.group(0)

    def redact_tax_code(match: re.Match[str]) -> str:
        candidate = match.group(0).upper()
        return "[REDACTED_TAX_CODE]" if is_valid_tax_code(candidate) else match.group(0)

    redacted = IBAN_IN_TEXT_PATTERN.sub(redact_iban, redacted)
    redacted = TAX_CODE_IN_TEXT_PATTERN.sub(redact_tax_code, redacted)
    redacted = PHONE_IN_TEXT_PATTERN.sub("[REDACTED_PHONE]", redacted)
    names = sorted({" ".join(name.strip().split()) for name in known_names if name.strip()}, key=lambda item: (-len(item), item.casefold()))
    for name in names:
        redacted = re.sub(rf"\b{re.escape(name)}\b", "[REDACTED_NAME]", redacted, flags=re.IGNORECASE)
    return redacted


def preserve_technical_key(
    value: T, *, column: str, approved_columns: set[str]
) -> T:
    if column not in approved_columns:
        raise InvalidConfigurationError("Technical key preservation is not approved for the requested column.")
    return value


def preserve_value(value: T) -> T:
    return value


def review_before_masking(value: T, *, column: str) -> T:
    if value is None:
        return value
    raise ReviewRequiredError(f"Masking is blocked pending explicit review for column {column}.")


def resolve_collisions(
    values: Iterable[str], *, normalizer: Callable[[str], str],
    candidate_generator: Callable[[str, int], str], max_attempts: int = 100,
) -> CollisionResolution:
    if max_attempts < 1:
        raise InvalidConfigurationError("max_attempts must be at least 1.")
    normalized_values = sorted({normalizer(value) for value in values})
    mapping: dict[str, str] = {}
    used_outputs: set[str] = set()
    collisions_detected = 0
    values_retried = 0
    maximum_attempts_used = 1 if normalized_values else 0
    for normalized_value in normalized_values:
        resolved = False
        for counter in range(max_attempts):
            attempts = counter + 1
            maximum_attempts_used = max(maximum_attempts_used, attempts)
            candidate = candidate_generator(normalized_value, counter)
            if candidate in used_outputs:
                collisions_detected += 1
                continue
            mapping[normalized_value] = candidate
            used_outputs.add(candidate)
            values_retried += int(counter > 0)
            resolved = True
            break
        if not resolved:
            raise UnresolvableCollisionError(
                "A deterministic collision could not be resolved within the configured attempt limit."
            )
    return CollisionResolution(
        mapping=mapping,
        statistics=CollisionStatistics(
            values_processed=len(normalized_values), collisions_detected=collisions_detected,
            collisions_resolved=values_retried, maximum_attempts=maximum_attempts_used,
        ),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml_path(path)


def validate_masking_configuration(
    registry_path: Path = REGISTRY_PATH,
    rules_path: Path = MASKING_RULES_PATH,
    groups_path: Path = CONSISTENCY_GROUPS_PATH,
) -> dict[str, int]:
    registry = _load_yaml(registry_path)["columns"]
    rules = _load_yaml(rules_path)["rules"]
    groups = _load_yaml(groups_path)["groups"]
    registry_by_column = {
        f"{record['schema_name']}.{record['table_name']}.{record['column_name']}": record
        for record in registry
    }
    unknown_rules = sorted({record["masking_rule"] for record in registry} - set(rules))
    unknown_groups = sorted({record["consistency_group"] for record in registry if record["consistency_group"]} - set(groups))
    if unknown_rules or unknown_groups:
        raise InvalidConfigurationError(
            f"Registry references undefined masking configuration: rules={unknown_rules}; groups={unknown_groups}"
        )
    namespaces = [group["namespace"] for group in groups.values()]
    if len(namespaces) != len(set(namespaces)):
        raise InvalidConfigurationError("Consistency group namespaces must be unique.")

    configured_membership: dict[str, str] = {}
    for group_name, group in groups.items():
        for column in group["columns"]:
            if column not in registry_by_column:
                raise InvalidConfigurationError(f"Consistency group {group_name} references an unknown registry column.")
            if column in configured_membership:
                raise InvalidConfigurationError("A registry column cannot belong to multiple consistency groups.")
            configured_membership[column] = group_name
            record = registry_by_column[column]
            if record["data_domain"] != group["data_domain"] or record["data_subject"] != group["data_subject"]:
                raise InvalidConfigurationError(f"Consistency group {group_name} has an incompatible domain or subject.")
    expected_membership = {
        column: record["consistency_group"]
        for column, record in registry_by_column.items() if record["consistency_group"]
    }
    if configured_membership != expected_membership:
        raise InvalidConfigurationError("Consistency group membership does not match the Privacy Metadata Registry.")

    for record in registry:
        if record["pii_category"] == "Non-PII" and record["masking_rule"] != "preserve_value":
            raise InvalidConfigurationError("Every Non-PII column must use preserve_value.")
        if record["pii_category"] == "Dubbio" and record["masking_rule"] != "review_before_masking":
            raise InvalidConfigurationError("Every Dubbio column must use review_before_masking.")
        if record["pii_category"] == "PII-nascosta" and record["data_domain"] == "free_text_with_pii" and record["masking_rule"] != "redact_free_text":
            raise InvalidConfigurationError("Hidden PII in free text must use redact_free_text.")
    return {
        "registry_columns": len(registry), "masking_rules": len(rules),
        "consistency_groups": len(groups), "grouped_columns": len(configured_membership),
    }


SYNTHETIC_RULE_EXAMPLES = {
    "mask_person_name": "[REDACTED_NAME] → Persona_token",
    "mask_email": "u***@example.test → u_token@example.test",
    "mask_phone": "+39******001 → +39 000 0000001",
    "mask_tax_code": "ABCDEF********** → QWERTY00A01Z000R",
    "mask_iban": "IT************************* → ITxxX0000000000xxxxxxxxxxxx",
    "shift_birth_date": "1980-**-** → data entro ±30 giorni",
    "redact_free_text": "Contatto sintetico → [REDACTED_EMAIL]",
    "preserve_technical_key": "1001 → 1001",
    "preserve_value": "aggregato → aggregato",
    "review_before_masking": "valore ambiguo → esecuzione bloccata",
    "mask_contact_value": "contatto sintetico → formato email o telefono sintetico",
    "mask_postal_address": "[REDACTED_ADDRESS] → Indirizzo sintetico token",
}


def render_masking_documentation(
    rules_path: Path = MASKING_RULES_PATH,
    groups_path: Path = CONSISTENCY_GROUPS_PATH,
) -> str:
    rules = _load_yaml(rules_path)["rules"]
    groups = _load_yaml(groups_path)["groups"]
    lines = [
        "# Regole di masking", "",
        "> Documento generato deterministicamente dalle configurazioni YAML. Nessun secret è incluso.", "",
        "## Principi", "",
        "Le pseudonimizzazioni usano `HMAC-SHA-256(secret, namespace + ':' + valore_normalizzato)` e namespace distinti. I mapping di collisione esistono soltanto in memoria.", "",
        "## Consistency group", "",
        "| Gruppo | Dominio | Soggetto | Namespace | Normalizzazione | Formato | Colonne |", "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, group in groups.items():
        lines.append(
            f"| {name} | {group['data_domain']} | {group['data_subject']} | `{group['namespace']}` | "
            f"{group['normalization']} | {group['output_format']} | {', '.join(group['columns'])} |"
        )
    lines.extend(["", "## Regole", ""])
    for name, rule in rules.items():
        lines.extend([
            f"### `{name}`", "",
            f"- **Scopo e input:** domini `{', '.join(rule['domains'])}`; trasformazione `{rule['transformation_type']}`.",
            f"- **Normalizzazione:** `{rule['normalization']}`.",
            f"- **Algoritmo:** `{rule['algorithm']}`.",
            f"- **Output:** `{rule['output_format']}`; esempio sintetico: `{SYNTHETIC_RULE_EXAMPLES[name]}`.",
            f"- **Determinismo e namespace:** deterministico={str(rule['deterministic']).lower()}; il namespace è fornito dal consistency group o dal contesto del soggetto.",
            f"- **NULL e stringhe vuote:** `{rule['null_handling']}` / `{rule['empty_string_handling']}`.",
            f"- **Collisioni:** `{rule['collision_handling']}`.",
            f"- **Impatto analitico:** {rule['analytical_impact']}",
            f"- **Limiti:** {rule['limitations']}", "",
        ])
    lines.extend([
        "## Trasferimento concettuale verso Informatica", "",
        "Le configurazioni locali rappresentano concetti di dominio, regola e coerenza cross-tabella trasferibili a una piattaforma enterprise. Nomi, disponibilità e comportamento delle funzioni specifiche di Informatica Data Privacy Management dovranno essere verificati quando la licenza sarà disponibile; questo documento non attribuisce funzionalità non osservate.", "",
    ])
    return "\n".join(lines)


def write_masking_documentation(path: Path = DOCUMENTATION_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_masking_documentation(), encoding="utf-8")


def main() -> None:
    summary = validate_masking_configuration()
    write_masking_documentation()
    print(
        f"Masking configuration valid: {summary['registry_columns']} registry columns, "
        f"{summary['masking_rules']} rules, {summary['consistency_groups']} consistency groups."
    )
    print(f"Written: {DOCUMENTATION_PATH}")


if __name__ == "__main__":
    main()
