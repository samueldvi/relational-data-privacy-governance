from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsistencyGroup:
    name: str
    data_domain: str
    data_subject: str
    namespace: str
    normalization: str
    columns: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("A consistency group must contain at least one column.")
