from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PhaseResult:
    name: str
    duration_seconds: float
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    phases: tuple[PhaseResult, ...]
    rows: int
    classified_columns: int
    masked_tables: int
    validations: int
    checksum: str

    @property
    def successful_phase_names(self) -> tuple[str, ...]:
        return tuple(phase.name for phase in self.phases)
