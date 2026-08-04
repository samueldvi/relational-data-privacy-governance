"""End-to-end command line interface for the privacy governance pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Sequence

import yaml
from psycopg import sql

from src.apply_masking import (
    MASKED_SCHEMAS,
    SOURCE_SCHEMAS,
    apply_masking,
    dry_run_plan,
    validate_only,
)
from src.classify import generate_classification
from src.db import get_connection
from src.generate_data import DEFAULT_SEED, load_dataset
from src.inventory import generate_inventory
from src.masking_manifest import MANIFEST_PATH
from src.profile_columns import generate_profiling


REGISTRY_PATH = Path("config/pii_registry.yml")
EXPECTED_SOURCE_TABLES = 20
EXPECTED_REGISTRY_COLUMNS = 109


def _safe_error(error: Exception) -> str:
    message = str(error).replace("\n", " ").strip()
    for variable in ("POSTGRES_PASSWORD", "MASKING_SECRET"):
        value = os.environ.get(variable)
        if value:
            message = message.replace(value, "[REDACTED]")
    if not message:
        message = error.__class__.__name__
    return message[:500]


def _git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True,
            check=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() or "detached"


def _count_tables_and_rows(cursor: Any, schemas: tuple[str, ...]) -> tuple[int, int]:
    cursor.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type='BASE TABLE' AND table_schema = ANY(%s)
        ORDER BY table_schema, table_name
        """,
        (list(schemas),),
    )
    tables = cursor.fetchall()
    rows = 0
    for schema_name, table_name in tables:
        cursor.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema_name), sql.Identifier(table_name)
            )
        )
        rows += cursor.fetchone()[0]
    return len(tables), rows


def command_generate(args: argparse.Namespace) -> dict[str, Any]:
    counts = load_dataset(args.seed)
    summary = {"seed": args.seed, "tables": len(counts), "rows": sum(counts.values())}
    print(
        f"Synthetic dataset generated: seed={summary['seed']}, "
        f"tables={summary['tables']}, rows={summary['rows']}."
    )
    return summary


def command_inventory(_: argparse.Namespace) -> dict[str, Any]:
    summary = generate_inventory()
    print(
        "Inventory generated: "
        f"schemas={summary['schemas']}, tables={summary['tables']}, columns={summary['columns']}, "
        f"PK={summary['primary_keys']}, FK={summary['foreign_keys']}, "
        f"UNIQUE={summary['unique_constraints']}, CHECK={summary['check_constraints']}."
    )
    return summary


def command_profile(_: argparse.Namespace) -> dict[str, Any]:
    result = generate_profiling()
    metadata = result["metadata"]
    print(
        f"Profiling generated: columns={metadata['column_count']}, "
        f"pattern_evidence={metadata['pattern_evidence_column_count']}, "
        f"privacy_patterns={metadata['suspicious_column_count']}, "
        f"redacted_samples={metadata['redacted_sample_count']}."
    )
    return metadata


def command_classify(_: argparse.Namespace) -> dict[str, Any]:
    records = generate_classification()
    if len(records) != EXPECTED_REGISTRY_COLUMNS or any(
        not record.get("pii_category") or not record.get("masking_rule") for record in records
    ):
        raise ValueError("Registry classification is incomplete.")
    categories = Counter(record["pii_category"] for record in records)
    statuses = Counter(record["review_status"] for record in records)
    print(
        f"Classification generated: columns={len(records)}; categories="
        + ",".join(f"{key}:{categories[key]}" for key in sorted(categories))
        + "; review="
        + ",".join(f"{key}:{statuses[key]}" for key in sorted(statuses))
        + "."
    )
    return {"columns": len(records), "categories": dict(categories), "statuses": dict(statuses)}


def command_mask(args: argparse.Namespace) -> dict[str, Any]:
    if args.dry_run:
        plan = dry_run_plan()
        print(
            f"Mask dry-run valid: tables={plan['tables']}, batches={plan['batch_sets']}, "
            f"strategy={plan['ambiguous_strategy']}, writes=0."
        )
        return plan
    if args.validate_only:
        result = validate_only()
        summary = {
            "tables": len(result["masked_counts"]),
            "rows": sum(result["masked_counts"].values()),
            "validations": len(result["validations"]),
        }
        print(
            f"Masked state valid: tables={summary['tables']}, rows={summary['rows']}, "
            f"validations={summary['validations']}."
        )
        return summary
    manifest = apply_masking()
    print(
        f"Masking completed: tables={manifest['tables_processed']}, "
        f"rows={sum(manifest['masked_rows_by_table'].values())}, "
        f"validations={len(manifest['validations'])}, checksum={manifest['global_checksum']}."
    )
    return manifest


def _read_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError("Masking manifest is not available.")
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if document.get("final_status") != "success":
        raise ValueError("Masking manifest does not report success.")
    return document


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    result = validate_only()
    manifest = _read_manifest()
    if manifest.get("table_checksums") != result["table_checksums"]:
        raise ValueError("Manifest checksums do not match the current masked state.")
    idempotent = None
    if args.check_idempotence:
        with tempfile.TemporaryDirectory(prefix="privacy-governance-validation-") as directory:
            first = apply_masking(manifest_path=Path(directory) / "first.json")
            second = apply_masking(manifest_path=Path(directory) / "second.json")
        idempotent = first == second
        if not idempotent:
            raise ValueError("Equivalent masking executions are not deterministic.")
    summary = {
        "tables": len(result["masked_counts"]),
        "rows": sum(result["masked_counts"].values()),
        "validations": len(result["validations"]),
        "checksum": manifest["global_checksum"],
        "idempotent": idempotent,
    }
    suffix = ", idempotence=verified" if idempotent else ""
    print(
        f"Validation successful: tables={summary['tables']}, rows={summary['rows']}, "
        f"checks={summary['validations']}, checksum={summary['checksum']}{suffix}."
    )
    return summary


def command_status(_: argparse.Namespace) -> dict[str, Any]:
    registry_columns = 0
    if REGISTRY_PATH.is_file():
        registry_columns = len(yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))["columns"])
    manifest = None
    if MANIFEST_PATH.is_file():
        try:
            manifest = _read_manifest()
        except (OSError, ValueError, json.JSONDecodeError):
            manifest = None
    with get_connection() as connection, connection.cursor() as cursor:
        source_tables, source_rows = _count_tables_and_rows(cursor, SOURCE_SCHEMAS)
        masked_tables, masked_rows = _count_tables_and_rows(cursor, MASKED_SCHEMAS)
    ready = all((
        source_tables == EXPECTED_SOURCE_TABLES,
        masked_tables == EXPECTED_SOURCE_TABLES,
        source_rows == masked_rows and source_rows > 0,
        registry_columns == EXPECTED_REGISTRY_COLUMNS,
        manifest is not None,
    ))
    status = "ready" if ready else "incomplete"
    summary = {
        "postgresql": "reachable", "source_schemas": len(SOURCE_SCHEMAS),
        "source_tables": source_tables, "source_rows": source_rows,
        "masked_tables": masked_tables, "masked_rows": masked_rows,
        "registry": "available" if registry_columns else "missing",
        "registry_columns": registry_columns,
        "manifest": "available" if manifest else "missing_or_invalid",
        "last_validation": "available" if manifest and manifest.get("validations") else "unavailable",
        "branch": _git_branch(), "status": status,
    }
    print(
        "Project status: "
        f"postgresql={summary['postgresql']}, source_schemas={summary['source_schemas']}, "
        f"source_tables={source_tables}, source_rows={source_rows}, "
        f"masked_tables={masked_tables}, masked_rows={masked_rows}, "
        f"registry={summary['registry']}({registry_columns}), manifest={summary['manifest']}, "
        f"last_validation={summary['last_validation']}, branch={summary['branch']}, status={status}."
    )
    return summary


def command_all(args: argparse.Namespace) -> dict[str, Any]:
    phases: list[tuple[str, Callable[[argparse.Namespace], dict[str, Any]], argparse.Namespace]] = [
        ("generate", command_generate, argparse.Namespace(seed=args.seed)),
        ("inventory", command_inventory, argparse.Namespace()),
        ("profile", command_profile, argparse.Namespace()),
        ("classify", command_classify, argparse.Namespace()),
        ("mask", command_mask, argparse.Namespace(dry_run=False, validate_only=False)),
        ("validate", command_validate, argparse.Namespace(check_idempotence=args.check_idempotence)),
    ]
    results: dict[str, Any] = {}
    timings: list[tuple[str, float]] = []
    for name, function, phase_args in phases:
        started = perf_counter()
        results[name] = function(phase_args)
        timings.append((name, perf_counter() - started))
    manifest = results["mask"]
    print("End-to-end summary:")
    for name, duration in timings:
        print(f"- {name}: success ({duration:.3f}s)")
    print(
        f"- result: rows={sum(manifest['masked_rows_by_table'].values())}, "
        f"classified_columns={results['classify']['columns']}, "
        f"masked_tables={manifest['tables_processed']}, "
        f"validations={len(manifest['validations'])}, checksum={manifest['global_checksum']}."
    )
    return {"phases": results, "timings": timings}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relational data privacy governance pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate deterministic synthetic data")
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED)
    generate.set_defaults(handler=command_generate)
    for name, help_text, handler in (
        ("inventory", "Generate the technical inventory", command_inventory),
        ("profile", "Profile source columns", command_profile),
        ("classify", "Generate the Privacy Metadata Registry", command_classify),
        ("status", "Show aggregate project readiness", command_status),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.set_defaults(handler=handler)
    mask = subparsers.add_parser("mask", help="Load or validate masked schemas")
    mask_mode = mask.add_mutually_exclusive_group()
    mask_mode.add_argument("--dry-run", action="store_true")
    mask_mode.add_argument("--validate-only", action="store_true")
    mask.set_defaults(handler=command_mask)
    validate = subparsers.add_parser("validate", help="Validate masked state and manifest")
    validate.add_argument("--check-idempotence", action="store_true")
    validate.set_defaults(handler=command_validate)
    all_command = subparsers.add_parser("all", help="Run the complete pipeline")
    all_command.add_argument("--seed", type=int, default=DEFAULT_SEED)
    all_command.add_argument("--check-idempotence", action="store_true")
    all_command.set_defaults(handler=command_all)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except Exception as error:  # CLI boundary: intentionally converts failures to safe exit codes.
        print(f"{args.command} failed: {_safe_error(error)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
