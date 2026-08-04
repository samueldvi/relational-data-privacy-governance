from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PiiCategory(StrEnum):
    DIRECT = "PII-diretta"
    INDIRECT = "PII-indiretta"
    HIDDEN = "PII-nascosta"
    NON_PII = "Non-PII"
    AMBIGUOUS = "Dubbio"


class ReviewStatus(StrEnum):
    AUTO_PROPOSED = "auto_proposed"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE_CONFIRMED = "false_positive_confirmed"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class ClassificationRecord:
    schema_name: str
    table_name: str
    column_name: str
    pii_category: PiiCategory
    data_domain: str
    data_subject: str
    masking_rule: str
    review_status: ReviewStatus
    confidence: float
    consistency_group: str | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}.{self.column_name}"

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("Classification confidence must be between zero and one.")
