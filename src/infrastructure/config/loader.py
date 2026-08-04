from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.shared.errors import ConfigurationError


CONFIG_DIRECTORY = Path("config")


def load_yaml_path(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as input_file:
            document = yaml.safe_load(input_file)
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Unable to load configuration {path}.") from error
    if not isinstance(document, dict):
        raise ConfigurationError(f"Configuration {path} must contain a mapping document.")
    return document


def write_yaml_path(
    path: Path, document: dict[str, Any], *, sort_keys: bool = False, width: int = 120
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=sort_keys, width=width),
            encoding="utf-8",
        )
    except OSError as error:
        raise ConfigurationError(f"Unable to write configuration {path}.") from error


class RepositoryConfigLoader:
    """Single entry point for versioned YAML configuration documents."""

    def __init__(self, directory: Path = CONFIG_DIRECTORY) -> None:
        self._directory = directory

    def load(self, name: str) -> dict[str, Any]:
        filename = name if name.endswith((".yml", ".yaml")) else f"{name}.yml"
        return load_yaml_path(self._directory / filename)
