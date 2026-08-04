from __future__ import annotations

import pytest

from src.domain.models import (
    ClassificationRecord,
    ConsistencyGroup,
    MaskingManifest,
    MaskingRule,
    PiiCategory,
    ReviewStatus,
    TableManifest,
)


def test_closed_domain_sets_match_versioned_vocabulary() -> None:
    assert len(PiiCategory) == 5
    assert len(MaskingRule) == 12
    assert ReviewStatus.REVIEW_REQUIRED == "review_required"


def test_classification_record_exposes_stable_qualified_name() -> None:
    record = ClassificationRecord(
        schema_name="crm", table_name="clienti", column_name="email",
        pii_category=PiiCategory.DIRECT, data_domain="email_address",
        data_subject="customer", masking_rule=MaskingRule.MASK_EMAIL,
        review_status=ReviewStatus.CONFIRMED, confidence=1.0,
        consistency_group="customer_email",
    )
    assert record.qualified_name == "crm.clienti.email"
    with pytest.raises(ValueError, match="confidence"):
        ClassificationRecord(
            "crm", "clienti", "email", PiiCategory.DIRECT, "email_address",
            "customer", MaskingRule.MASK_EMAIL, ReviewStatus.CONFIRMED, 1.1,
        )


def test_consistency_groups_require_columns() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ConsistencyGroup("empty", "email", "customer", "email.customer", "lower", ())


def test_manifest_total_rows_is_derived_from_tables() -> None:
    manifest = MaskingManifest(
        format_version=1, algorithm="HMAC-SHA-256",
        tables=(TableManifest("masked_crm.clienti", 150, 150, "a" * 64),),
        load_order=("crm.clienti",), validations=("row_counts",),
        global_checksum="b" * 64, final_status="success",
    )
    assert manifest.total_rows == 150
