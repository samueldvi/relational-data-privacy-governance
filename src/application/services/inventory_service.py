from __future__ import annotations

from collections.abc import Callable
from typing import Any


class InventoryService:
    def __init__(self, generate_inventory: Callable[[], dict[str, Any]]) -> None:
        self._generate_inventory = generate_inventory

    def run(self) -> dict[str, Any]:
        return self._generate_inventory()
