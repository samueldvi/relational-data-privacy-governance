"""Composition root wiring application services to concrete local adapters."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from src.application.context import ApplicationContext
from src.application.pipeline import EndToEndPipeline
from src.application.services import (
    ClassificationService,
    GenerationService,
    InventoryService,
    MaskingService,
    ProfilingService,
    SchemaDriftService,
    StatusService,
    ValidationService,
)
from src.apply_masking import apply_masking, dry_run_plan, validate_only
from src.classify import generate_classification
from src.generate_data import load_dataset
from src.infrastructure.database.connection import connection_factory
from src.infrastructure.database.schema_metadata_reader import PostgresSchemaMetadataReader
from src.infrastructure.serialization.json_manifest_repository import JsonManifestRepository
from src.infrastructure.serialization.schema_baseline_repository import SchemaBaselineRepository
from src.infrastructure.status.project_status import ProjectStatusProvider
from src.inventory import generate_inventory
from src.masking import CONSISTENCY_GROUPS_PATH, MASKING_RULES_PATH, REGISTRY_PATH
from src.masking_manifest import MANIFEST_PATH
from src.profile_columns import generate_profiling


def build_application() -> ApplicationContext:
    manifest_repository = JsonManifestRepository(MANIFEST_PATH)
    schema_reader = PostgresSchemaMetadataReader(
        connection_factory(),
        ("billing", "crm", "hr"),
        REGISTRY_PATH,
        MASKING_RULES_PATH,
        CONSISTENCY_GROUPS_PATH,
    )
    return ApplicationContext(
        generation=GenerationService(load_dataset),
        inventory=InventoryService(generate_inventory),
        profiling=ProfilingService(generate_profiling),
        classification=ClassificationService(generate_classification),
        masking=MaskingService(apply_masking, dry_run_plan, validate_only),
        validation=ValidationService(
            validate_only,
            manifest_repository.load,
            lambda path: apply_masking(manifest_path=path),
        ),
        status=StatusService(ProjectStatusProvider(connection_factory()).snapshot),
        drift=SchemaDriftService(schema_reader, SchemaBaselineRepository(Path("config/schema_baseline.yml"))),
    )


def build_pipeline(context: ApplicationContext) -> EndToEndPipeline:
    return EndToEndPipeline(context, perf_counter)
