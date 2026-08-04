from __future__ import annotations

from typing import Any, Protocol


class ConfigurationLoader(Protocol):
    def load(self, name: str) -> dict[str, Any]: ...


class SecretProvider(Protocol):
    def masking_secret(self) -> str: ...
