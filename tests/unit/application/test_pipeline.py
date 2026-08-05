from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.application.context import ApplicationContext
from src.application.pipeline import PIPELINE_PHASES, EndToEndPipeline
from src.application.services import (
    ClassificationService,
    GenerationService,
    InventoryService,
    MaskingService,
    ProfilingService,
    StatusService,
    ValidationService,
)
from src.shared.errors import RegistryValidationError


def test_pipeline_has_one_authoritative_order_and_stops_on_first_error() -> None:
    order = []

    def record(name, result):
        return lambda *args, **kwargs: order.append(name) or result

    context = ApplicationContext(
        generation=GenerationService(record("generate", {"crm.a": 2})),
        inventory=InventoryService(record("inventory", {})),
        profiling=ProfilingService(record("profile", {"metadata": {}})),
        classification=ClassificationService(
            record(
                "classify",
                [
                    {
                        "pii_category": "Non-PII",
                        "masking_rule": "preserve_value",
                        "review_status": "confirmed",
                    }
                ],
            )
        ),
        masking=MaskingService(
            record(
                "mask",
                {
                    "masked_rows_by_table": {"crm.a": 2},
                    "tables_processed": 1,
                    "validations": ["rows"],
                    "global_checksum": "a" * 64,
                },
            ),
            Mock(),
            Mock(),
        ),
        validation=ValidationService(
            record(
                "validate",
                {
                    "masked_counts": {"crm.a": 2},
                    "table_checksums": {},
                    "validations": ["rows"],
                },
            ),
            lambda: {"table_checksums": {}, "global_checksum": "a" * 64},
            Mock(),
        ),
        status=StatusService(lambda: {}),
    )
    context.classification._expected_columns = 1
    ticks = iter(range(20))
    result = EndToEndPipeline(context, lambda: next(ticks)).run(seed=1)
    assert tuple(order) == PIPELINE_PHASES
    assert result.rows == 2 and result.successful_phase_names == PIPELINE_PHASES


def test_classification_service_rejects_incomplete_registry() -> None:
    service = ClassificationService(lambda: [{"pii_category": "Dubbio"}], expected_columns=1)
    with pytest.raises(RegistryValidationError, match="incomplete"):
        service.run()


def test_masking_service_rejects_conflicting_modes() -> None:
    service = MaskingService(Mock(), Mock(), Mock())
    with pytest.raises(ValueError, match="mutually exclusive"):
        service.run(dry_run=True, validate_only=True)
