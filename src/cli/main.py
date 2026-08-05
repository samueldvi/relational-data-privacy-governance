"""Argument parsing and safe presentation boundary."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from src.bootstrap import build_application, build_pipeline
from src.cli.commands import all as all_command
from src.cli.commands import classify, drift, generate, inventory, mask, profile, status, validate
from src.generate_data import DEFAULT_SEED
from src.shared.errors import PrivacyGovernanceError

COMMANDS = {
    "generate": generate.execute,
    "inventory": inventory.execute,
    "profile": profile.execute,
    "classify": classify.execute,
    "mask": mask.execute,
    "validate": validate.execute,
    "status": status.execute,
    "drift": drift.execute,
}


def _safe_error(error: Exception) -> str:
    if isinstance(error, PrivacyGovernanceError):
        return str(error).replace("\n", " ")[:500]
    return f"Unexpected {error.__class__.__name__}."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relational data privacy governance pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate", help="Generate deterministic synthetic data")
    generate_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    for name, help_text in (
        ("inventory", "Generate the technical inventory"),
        ("profile", "Profile source columns"),
        ("classify", "Generate the Privacy Metadata Registry"),
        ("status", "Show aggregate project readiness"),
    ):
        subparsers.add_parser(name, help=help_text)
    drift_parser = subparsers.add_parser("drift", help="Compare PostgreSQL metadata with the approved baseline")
    drift_mode = drift_parser.add_mutually_exclusive_group()
    drift_mode.add_argument("--check", action="store_true", help="Fail when drift is detected")
    drift_mode.add_argument(
        "--write-baseline",
        action="store_true",
        help="Explicitly replace the versioned baseline with current reviewed metadata",
    )
    mask_parser = subparsers.add_parser("mask", help="Load or validate masked schemas")
    mask_mode = mask_parser.add_mutually_exclusive_group()
    mask_mode.add_argument("--dry-run", action="store_true")
    mask_mode.add_argument("--validate-only", action="store_true")
    validate_parser = subparsers.add_parser("validate", help="Validate masked state and manifest")
    validate_parser.add_argument("--check-idempotence", action="store_true")
    all_parser = subparsers.add_parser("all", help="Run the complete pipeline")
    all_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    all_parser.add_argument("--check-idempotence", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        context = build_application()
        if args.command == "all":
            all_command.execute(context, build_pipeline(context), args)
        else:
            COMMANDS[args.command](context, args)
    except Exception as error:
        print(f"{args.command} failed: {_safe_error(error)}", file=sys.stderr)
        return 1
    return 0
