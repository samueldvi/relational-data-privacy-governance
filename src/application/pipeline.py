from __future__ import annotations

from collections.abc import Callable

from src.application.context import ApplicationContext
from src.application.dto import PhaseResult, PipelineResult

PIPELINE_PHASES = ("generate", "inventory", "profile", "classify", "mask", "validate")


class EndToEndPipeline:
    """The single authoritative ordering for the complete local pipeline."""

    def __init__(self, context: ApplicationContext, monotonic: Callable[[], float]) -> None:
        self._context = context
        self._monotonic = monotonic

    def run(self, *, seed: int, check_idempotence: bool = False) -> PipelineResult:
        operations = (
            ("generate", lambda: self._context.generation.run(seed)),
            ("inventory", self._context.inventory.run),
            ("profile", self._context.profiling.run),
            ("classify", self._context.classification.run),
            ("mask", self._context.masking.run),
            ("validate", lambda: self._context.validation.run(check_idempotence=check_idempotence)),
        )
        results: dict[str, dict] = {}
        phases = []
        for name, operation in operations:
            started = self._monotonic()
            metrics = operation()
            phases.append(PhaseResult(name, self._monotonic() - started, metrics))
            results[name] = metrics
        manifest = results["mask"]
        return PipelineResult(
            phases=tuple(phases),
            rows=sum(manifest["masked_rows_by_table"].values()),
            classified_columns=results["classify"]["columns"],
            masked_tables=manifest["tables_processed"],
            validations=len(manifest["validations"]),
            checksum=manifest["global_checksum"],
        )
