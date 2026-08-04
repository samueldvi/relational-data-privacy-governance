from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RelationshipStatus(StrEnum):
    DECLARED = "declared"
    LOGICAL_CONFIRMED = "logical_confirmed"
    LOGICAL_SUSPECTED = "logical_suspected"
    NOT_CONFIRMED = "not_confirmed"


@dataclass(frozen=True, slots=True)
class Relationship:
    source_column: str
    target_column: str
    status: RelationshipStatus
    matched_distinct_count: int = 0
    orphan_count: int = 0
    cross_schema: bool = False
