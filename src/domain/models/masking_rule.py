from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MaskingRule(StrEnum):
    MASK_PERSON_NAME = "mask_person_name"
    MASK_EMAIL = "mask_email"
    MASK_PHONE = "mask_phone"
    MASK_TAX_CODE = "mask_tax_code"
    MASK_IBAN = "mask_iban"
    SHIFT_BIRTH_DATE = "shift_birth_date"
    REDACT_FREE_TEXT = "redact_free_text"
    PRESERVE_TECHNICAL_KEY = "preserve_technical_key"
    PRESERVE_VALUE = "preserve_value"
    REVIEW_BEFORE_MASKING = "review_before_masking"
    MASK_CONTACT_VALUE = "mask_contact_value"
    MASK_POSTAL_ADDRESS = "mask_postal_address"


@dataclass(frozen=True, slots=True)
class MaskingStatistics:
    values_processed: int = 0
    collisions_detected: int = 0
    collisions_resolved: int = 0
    maximum_attempts: int = 0
