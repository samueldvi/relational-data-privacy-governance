from __future__ import annotations

from dataclasses import dataclass

from src.application.services import (
    ClassificationService,
    GenerationService,
    InventoryService,
    MaskingService,
    ProfilingService,
    StatusService,
    ValidationService,
)


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    generation: GenerationService
    inventory: InventoryService
    profiling: ProfilingService
    classification: ClassificationService
    masking: MaskingService
    validation: ValidationService
    status: StatusService
