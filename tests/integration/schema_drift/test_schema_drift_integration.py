from __future__ import annotations

from pathlib import Path

from src.application.services.schema_drift_service import SchemaDriftService
from src.infrastructure.database.connection import connection_factory
from src.infrastructure.database.schema_metadata_reader import PostgresSchemaMetadataReader
from src.infrastructure.serialization.schema_baseline_repository import SchemaBaselineRepository
from src.masking import CONSISTENCY_GROUPS_PATH, MASKING_RULES_PATH, REGISTRY_PATH


def _reader() -> PostgresSchemaMetadataReader:
    return PostgresSchemaMetadataReader(
        connection_factory(),
        ("billing", "crm", "hr"),
        REGISTRY_PATH,
        MASKING_RULES_PATH,
        CONSISTENCY_GROUPS_PATH,
    )


def test_versioned_baseline_matches_current_database_and_governance() -> None:
    report = SchemaDriftService(_reader(), SchemaBaselineRepository(Path("config/schema_baseline.yml"))).report()
    assert report.items == ()


def test_baseline_serialization_round_trip_is_deterministic(tmp_path: Path) -> None:
    snapshot = _reader().snapshot()
    repository = SchemaBaselineRepository(tmp_path / "baseline.yml")
    repository.save(snapshot)
    first = repository.path.read_bytes()
    assert repository.load() == snapshot
    repository.save(repository.load())
    assert repository.path.read_bytes() == first
