"""Public CLI package; use ``python -m src.cli``."""

from src.cli.main import build_parser, main

__all__ = ["build_parser", "main"]
