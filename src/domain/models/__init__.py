"""Typed domain models shared across privacy-governance modules."""

from src.domain.models.classification import (
    ClassificationRecord,
    PiiCategory,
    ReviewStatus,
)
from src.domain.models.consistency_group import ConsistencyGroup
from src.domain.models.manifest import MaskingManifest, TableManifest
from src.domain.models.masking_rule import MaskingRule, MaskingStatistics
from src.domain.models.metadata import ColumnMetadata, ColumnProfile
from src.domain.models.relationship import Relationship, RelationshipStatus
from src.domain.models.validation import ValidationResult

__all__ = [
    "ClassificationRecord", "ColumnMetadata", "ColumnProfile", "ConsistencyGroup",
    "MaskingManifest", "MaskingRule", "MaskingStatistics", "PiiCategory",
    "Relationship", "RelationshipStatus", "ReviewStatus", "TableManifest",
    "ValidationResult",
]
