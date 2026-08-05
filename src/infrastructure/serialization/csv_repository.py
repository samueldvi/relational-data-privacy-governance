from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


class CsvRepository:
    def read(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as input_file:
            return list(csv.DictReader(input_file))

    def write(self, path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
