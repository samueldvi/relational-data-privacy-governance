"""Normalizers used by evidence detection and cross-table comparisons."""

from __future__ import annotations

import re


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_tax_code(value: str) -> str:
    return value.strip().upper()


def normalize_iban(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def normalize_phone(value: str) -> str:
    stripped = value.strip()
    prefix = "+" if stripped.startswith("+") else ""
    return prefix + re.sub(r"\D", "", stripped)


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").strip()
