from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from src.domain.models import ClassificationRecord, ColumnMetadata, MaskingManifest, Relationship


class MetadataRepository(Protocol):
    def columns(self) -> Sequence[ColumnMetadata]: ...
    def relationships(self) -> Sequence[Relationship]: ...


class RegistryRepository(Protocol):
    def load(self) -> Sequence[ClassificationRecord]: ...
    def save(self, records: Sequence[ClassificationRecord]) -> None: ...


class ManifestRepository(Protocol):
    def load(self) -> MaskingManifest: ...
    def save(self, manifest: MaskingManifest | dict[str, Any]) -> None: ...
