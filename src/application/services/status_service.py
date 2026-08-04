from __future__ import annotations

from collections.abc import Callable
from typing import Any


class StatusService:
    def __init__(self, status_provider: Callable[[], dict[str, Any]]) -> None:
        self._status_provider = status_provider

    def run(self) -> dict[str, Any]:
        return self._status_provider()
