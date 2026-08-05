from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.application.services.schema_drift_service import SchemaDriftService
from src.domain.schema_drift import ColumnSnapshot, SchemaSnapshot, TableSnapshot
from src.shared.errors import SchemaDriftError


def _snapshot(*, classified: bool = True) -> SchemaSnapshot:
    return SchemaSnapshot(
        version=1,
        tables=(
            TableSnapshot(
                "crm",
                "clienti",
                (
                    ColumnSnapshot(
                        1,
                        "cliente_id",
                        "bigint",
                        "int8",
                        False,
                        "PII-indiretta" if classified else None,
                        "preserve_technical_key" if classified else None,
                        None,
                    ),
                ),
                (),
            ),
        ),
        logical_relationships=(),
        masking_rules=("preserve_technical_key",),
        consistency_groups=(),
    )


def test_service_compares_current_state_with_loaded_baseline() -> None:
    baseline, current, store = _snapshot(), _snapshot(), Mock()
    provider = Mock()
    provider.snapshot.return_value = current
    store.load.return_value = baseline
    assert SchemaDriftService(provider, store).report().has_drift is False
    store.load.assert_called_once_with()
    provider.snapshot.assert_called_once_with()


def test_explicit_baseline_write_persists_only_governed_snapshot() -> None:
    provider, store = Mock(), Mock()
    provider.snapshot.return_value = _snapshot()
    summary = SchemaDriftService(provider, store).write_baseline()
    assert summary == {"schemas": 1, "tables": 1, "columns": 1, "constraints": 0, "logical_relationships": 0}
    store.save.assert_called_once_with(provider.snapshot.return_value)


def test_baseline_write_is_blocked_for_unclassified_columns() -> None:
    provider, store = Mock(), Mock()
    provider.snapshot.return_value = _snapshot(classified=False)
    with pytest.raises(SchemaDriftError, match="governance issue"):
        SchemaDriftService(provider, store).write_baseline()
    store.save.assert_not_called()
