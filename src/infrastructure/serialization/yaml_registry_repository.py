from __future__ import annotations

from pathlib import Path
from typing import Any

from src.infrastructure.config.loader import load_yaml_path, write_yaml_path


class YamlRegistryRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_document(self) -> dict[str, Any]:
        return load_yaml_path(self.path)

    def save_document(self, document: dict[str, Any]) -> None:
        write_yaml_path(self.path, document, sort_keys=False)
