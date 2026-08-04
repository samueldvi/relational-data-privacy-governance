from __future__ import annotations

from collections.abc import Callable


class GenerationService:
    def __init__(self, load_dataset: Callable[[int], dict[str, int]]) -> None:
        self._load_dataset = load_dataset

    def run(self, seed: int) -> dict[str, int]:
        counts = self._load_dataset(seed)
        return {"seed": seed, "tables": len(counts), "rows": sum(counts.values())}
