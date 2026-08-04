"""Side-effect-free deterministic masking transformations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypeVar

from src.domain.identifiers import (
    iban_mod97,
    is_valid_italian_iban,
    is_valid_tax_code,
    tax_code_check_character,
)
from src.shared.errors import (
    InvalidConfigurationError,
    MissingSecretError,
    ReviewRequiredError,
    UnresolvableCollisionError,
    UnsupportedFormatError,
    WeakSecretError,
)


MINIMUM_SECRET_LENGTH = 32
EMAIL_PATTERN = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
EMAIL_IN_TEXT_PATTERN = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
TAX_CODE_IN_TEXT_PATTERN = re.compile(r"\b[A-Z0-9]{16}\b", re.IGNORECASE)
IBAN_IN_TEXT_PATTERN = re.compile(r"\bIT(?:\s?[0-9A-Z]){25}\b", re.IGNORECASE)
PHONE_IN_TEXT_PATTERN = re.compile(r"(?<!\w)(?:(?:\+|00)39)?(?:[\s().-]*\d){8,11}(?!\w)")
T = TypeVar("T")


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
    return " ".join(value.strip().split()).casefold()


def mask_email(value: str | None, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    if value is None:
        return None
    normalized = normalize_email(value)
    return "" if not normalized else f"u_{_token(_digest(secret, namespace, normalized, counter), 20)}@example.test"


def mask_phone(value: str | None, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    if value is None:
        return None
    normalized = normalize_phone(value)
    if not normalized:
        return ""
    number = int.from_bytes(_digest(secret, namespace, normalized, counter)[:8], "big") % 10_000_000
    return f"+39 000 {number:07d}"


def mask_tax_code(value: str | None, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    if value is None:
        return None
    normalized = normalize_tax_code(value)
    if not normalized:
        return ""
    digest = _digest(secret, namespace, normalized, counter)
    letters, month_codes = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "ABCDEHLMPRST"
    prefix = "".join(letters[digest[index] % 26] for index in range(6))
    year = int.from_bytes(digest[6:8], "big") % 100
    month = month_codes[digest[8] % len(month_codes)]
    day = digest[9] % 31 + 1 + (40 if digest[10] % 2 else 0)
    municipality = letters[digest[11] % 26] + f"{int.from_bytes(digest[12:14], 'big') % 1000:03d}"
    body = f"{prefix}{year:02d}{month}{day:02d}{municipality}"
    return body + tax_code_check_character(body)


def mask_iban(value: str | None, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    if value is None:
        return None
    normalized = normalize_iban(value)
    if not normalized:
        return ""
    digest = _digest(secret, namespace, normalized, counter)
    cin = chr(65 + digest[0] % 26)
    account_number = int.from_bytes(digest[1:9], "big") % 1_000_000_000_000
    bban = f"{cin}0000000000{account_number:012d}"
    check_digits = 98 - iban_mod97(bban + "IT00")
    return f"IT{check_digits:02d}{bban}"


def mask_person_name(value: str | None, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    if value is None:
        return None
    normalized = normalize_name(value)
    if not normalized:
        return ""
    return " ".join(
        f"Persona_{_token(_digest(secret, namespace, f'{normalized}:token:{index}', counter), 8)}"
        for index, _ in enumerate(normalized.split())
    )


def mask_postal_address(value: str | None, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    if value is None:
        return None
    normalized = normalize_name(value)
    return "" if not normalized else f"Indirizzo sintetico {_token(_digest(secret, namespace, normalized, counter), 12)}"


def mask_contact_value(value: str | None, contact_type: str, *, secret: str, namespace: str, counter: int = 0) -> str | None:
    normalized_type = contact_type.strip().lower()
    if normalized_type in {"email", "pec"}:
        return mask_email(value, secret=secret, namespace=f"{namespace}.email", counter=counter)
    if normalized_type in {"telefono", "phone"}:
        return mask_phone(value, secret=secret, namespace=f"{namespace}.phone", counter=counter)
    raise UnsupportedFormatError("Contact type is not supported by mask_contact_value.")


def shift_birth_date(value: date | None, *, secret: str, namespace: str, reference_date: date) -> date | None:
    if value is None:
        return None
    if type(value) is not date:
        raise UnsupportedFormatError("Birth date must be a date value.")
    if value > reference_date:
        raise UnsupportedFormatError("Birth date cannot be after the explicit reference date.")
    raw_offset = int.from_bytes(_digest(secret, namespace, value.isoformat())[:2], "big") % 60
    offset = raw_offset - 30 if raw_offset < 30 else raw_offset - 29
    return min(value + timedelta(days=offset), reference_date)


def redact_free_text(text: str | None, *, known_names: Iterable[str] = ()) -> str | None:
    if text is None or text == "":
        return text
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


def preserve_technical_key(value: T, *, column: str, approved_columns: set[str]) -> T:
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
    collisions_detected = values_retried = 0
    maximum_attempts_used = 1 if normalized_values else 0
    for normalized_value in normalized_values:
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
            break
        else:
            raise UnresolvableCollisionError(
                "A deterministic collision could not be resolved within the configured attempt limit."
            )
    return CollisionResolution(mapping, CollisionStatistics(
        len(normalized_values), collisions_detected, values_retried, maximum_attempts_used
    ))


__all__ = [
    "CollisionResolution", "CollisionStatistics", "mask_contact_value", "mask_email",
    "mask_iban", "mask_person_name", "mask_phone", "mask_postal_address", "mask_tax_code",
    "normalize_email", "normalize_iban", "normalize_name", "normalize_phone",
    "normalize_tax_code", "preserve_technical_key", "preserve_value", "redact_free_text",
    "resolve_collisions", "review_before_masking", "shift_birth_date", "validate_secret",
]
