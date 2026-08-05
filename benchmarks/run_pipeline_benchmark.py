#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bootstrap import build_application, build_pipeline  # noqa: E402

DEFAULT_CONFIG = ROOT / "benchmarks/benchmark_config.yml"
DEFAULT_OUTPUT = ROOT / "output/benchmark_results.json"
DEFAULT_DOCUMENTATION = ROOT / "docs/PERFORMANCE_BASELINE.md"


def _commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False, timeout=10
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


def _output_size() -> int:
    output = ROOT / "output"
    return sum(path.stat().st_size for path in output.rglob("*") if path.is_file()) if output.exists() else 0


def run_profile(name: str, config: dict[str, Any], seed: int) -> dict[str, Any]:
    iterations = int(config["iterations"])
    phases: dict[str, float] = defaultdict(float)
    rows = 0
    started = perf_counter()
    for _ in range(iterations):
        result = build_pipeline(build_application()).run(seed=seed, check_idempotence=False)
        rows += result.rows
        for phase in result.phases:
            phases[phase.name] += phase.duration_seconds
    duration = perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = int(peak if platform.system() == "Darwin" else peak * 1024)
    return {
        "profile": name,
        "iterations": iterations,
        "configured_approximate_rows": int(config["approximate_rows"]),
        "processed_rows": rows,
        "phase_seconds": {phase: round(value, 6) for phase, value in sorted(phases.items())},
        "total_seconds": round(duration, 6),
        "rows_per_second": round(rows / duration, 2),
        "peak_memory_bytes": peak_bytes,
        "output_size_bytes": _output_size(),
    }


def render_document(results: dict[str, Any]) -> str:
    lines = [
        "# Performance baseline",
        "",
        "> Benchmark locale su dati esclusivamente sintetici; non è una validazione di capacità enterprise.",
        "",
        "## Ambiente",
        "",
        f"- Data UTC: `{results['environment']['timestamp_utc']}`",
        f"- Commit: `{results['environment']['commit'] or 'unavailable'}`",
        f"- Python: `{results['environment']['python']}`",
        f"- Sistema: `{results['environment']['platform']}`",
        "",
        "## Risultati locali",
        "",
        "| Profilo | Iterazioni | Righe cumulative | Secondi | Righe/s | Picco memoria | Output |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results["profiles"]:
        lines.append(
            f"| {item['profile']} | {item['iterations']} | {item['processed_rows']} | "
            f"{item['total_seconds']:.3f} | {item['rows_per_second']:.2f} | "
            f"{item['peak_memory_bytes']} B | {item['output_size_bytes']} B |"
        )
    lines.extend(
        [
            "",
            "## Durate per fase",
            "",
            "Le durate aggregate includono generazione, inventory, profiling, classificazione, masking e validazione.",
            "Il JSON allegato conserva il dettaglio numerico per fase.",
            "",
            "## Limiti",
            "",
            "I profili 20k e 100k rappresentano rispettivamente 10 e 49 esecuzioni complete cumulative del dataset "
            "baseline da 2.063 righe. Non dimostrano il comportamento di un singolo database con 20k o 100k righe, "
            "né concorrenza, saturazione, SLA o capacità enterprise. Tempi e memoria dipendono da hardware, Docker, "
            "carico del sistema e stato delle cache. Il benchmark non usa dati reali e non appartiene alla CI principale.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible synthetic pipeline benchmarks")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", action="append", dest="profiles")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    args = parser.parse_args()
    document = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    selected = args.profiles or list(document["profiles"])
    unknown = sorted(set(selected) - set(document["profiles"]))
    if unknown:
        parser.error(f"unknown profile(s): {', '.join(unknown)}")
    results = {
        "version": 1,
        "environment": {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "commit": _commit(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "profiles": [run_profile(name, document["profiles"][name], int(document["seed"])) for name in selected],
        "enterprise_validation": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.documentation.parent.mkdir(parents=True, exist_ok=True)
    args.documentation.write_text(render_document(results), encoding="utf-8")
    print(f"Benchmark complete: profiles={len(selected)}, output={args.output}, documentation={args.documentation}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
