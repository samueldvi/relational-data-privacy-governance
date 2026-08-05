from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ProfilingService:
    def __init__(self, generate_profiling: Callable[[], dict[str, Any]]) -> None:
        self._generate_profiling = generate_profiling

    def run(self) -> dict[str, Any]:
        metadata = self._generate_profiling().get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("Profiling output must contain mapping metadata.")
        return metadata
