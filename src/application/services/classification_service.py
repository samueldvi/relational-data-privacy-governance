from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from src.shared.errors import RegistryValidationError


class ClassificationService:
    def __init__(
        self,
        generate_classification: Callable[[], list[dict[str, Any]]],
        expected_columns: int = 109,
    ) -> None:
        self._generate_classification = generate_classification
        self._expected_columns = expected_columns

    def run(self) -> dict[str, Any]:
        records = self._generate_classification()
        if len(records) != self._expected_columns or any(
            not record.get("pii_category") or not record.get("masking_rule") for record in records
        ):
            raise RegistryValidationError("Registry classification is incomplete.")
        categories = Counter(record["pii_category"] for record in records)
        statuses = Counter(record["review_status"] for record in records)
        return {
            "columns": len(records),
            "categories": dict(sorted(categories.items())),
            "statuses": dict(sorted(statuses.items())),
        }
