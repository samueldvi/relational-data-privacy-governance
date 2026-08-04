#!/usr/bin/env python3
"""Check tracked repository files for likely secrets and sensitive artifacts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


SENSITIVE_FILENAMES = re.compile(
    r"(^|/)\.env$|(^|/)(?:credentials?|secrets?)(?:[./]|$)|"
    r"\.(?:dump|sql\.gz|pem|key|p12|pfx|swp|swo|tmp)$|~$",
    re.IGNORECASE,
)
SENSITIVE_OUTPUT = re.compile(
    r"^(?:output|data/generated)/|(?:^|/)(?:pii[-_.]?mapping|masking[-_.]?mapping)(?:[./]|$)",
    re.IGNORECASE,
)
CONTENT_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credentialed PostgreSQL DSN", re.compile(r"postgres(?:ql)?://[^\s:/]+:[^\s@]+@", re.IGNORECASE)),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)
ASSIGNMENT_PATTERN = re.compile(
    r"(?im)^\s*(?:POSTGRES_PASSWORD|MASKING_SECRET)\s*(?:=|:)\s*[\"']?([^\s\"'#]+)"
)
ALLOWED_MARKERS = (
    "change_me", "replace_with_", "synthetic", "not-for-production", "example", "placeholder",
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True, timeout=15,
    )
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def _is_allowed_test_value(value: str) -> bool:
    lowered = value.casefold()
    environment_reference = re.fullmatch(r"\$\{[A-Z][A-Z0-9_]*\}", value) is not None
    return environment_reference or any(marker in lowered for marker in ALLOWED_MARKERS)


def scan_files(paths: Iterable[Path], known_values: Iterable[str] = ()) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    known = [value for value in known_values if len(value) >= 8 and not _is_allowed_test_value(value)]
    for path in paths:
        normalized = path.as_posix()
        if SENSITIVE_FILENAMES.search(normalized):
            violations.append((normalized, "sensitive filename"))
            continue
        if SENSITIVE_OUTPUT.search(normalized):
            violations.append((normalized, "generated or mapping output is tracked"))
        try:
            payload = path.read_bytes()
        except OSError:
            violations.append((normalized, "tracked file cannot be read"))
            continue
        if b"\0" in payload:
            continue
        text = payload.decode("utf-8", errors="replace")
        for label, pattern in CONTENT_PATTERNS:
            if pattern.search(text):
                violations.append((normalized, label))
        for match in ASSIGNMENT_PATTERN.finditer(text):
            if not _is_allowed_test_value(match.group(1)):
                violations.append((normalized, "non-synthetic credential assignment"))
        for value in known:
            if value in text:
                violations.append((normalized, "current environment secret is tracked"))
                break
    return sorted(set(violations))


def main() -> int:
    try:
        files = tracked_files()
        violations = scan_files(
            files,
            known_values=(
                os.environ.get("MASKING_SECRET", ""),
                os.environ.get("POSTGRES_PASSWORD", ""),
            ),
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Repository safety check failed to inspect tracked files: {error.__class__.__name__}.", file=sys.stderr)
        return 2
    if violations:
        print(f"Repository safety check failed: {len(violations)} violation(s).", file=sys.stderr)
        for path, reason in violations:
            print(f"- {path}: {reason}", file=sys.stderr)
        return 1
    print(f"Repository safety check passed: {len(files)} tracked files inspected, 0 violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
