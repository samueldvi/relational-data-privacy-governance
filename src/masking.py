"""Compatibility facade for masking rules and configuration documentation.

Pure transformations live in :mod:`src.domain.masking`; file and environment
access remain here only for backwards-compatible entry points.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.domain.masking.primitives import (
    CollisionResolution,
    CollisionStatistics,
    mask_contact_value,
    mask_email,
    mask_iban,
    mask_person_name,
    mask_phone,
    mask_postal_address,
    mask_tax_code,
    normalize_email,
    normalize_iban,
    normalize_name,
    normalize_phone,
    normalize_tax_code,
    preserve_technical_key,
    preserve_value,
    redact_free_text,
    resolve_collisions,
    review_before_masking,
    shift_birth_date,
    validate_secret,
)
from src.infrastructure.config.loader import load_yaml_path
from src.infrastructure.security.secret_provider import EnvironmentSecretProvider
from src.shared.errors import (
    InvalidConfigurationError,
    MaskingError,
    MaskingSecretError,
    MissingSecretError,
    ReviewRequiredError,
    UnresolvableCollisionError,
    UnsupportedFormatError,
    WeakSecretError,
)


MASKING_RULES_PATH = Path("config/masking_rules.yml")
CONSISTENCY_GROUPS_PATH = Path("config/consistency_groups.yml")
REGISTRY_PATH = Path("config/pii_registry.yml")
DOCUMENTATION_PATH = Path("docs/REGOLE_MASCHERAMENTO.md")


def get_masking_secret() -> str:
    try:
        secret = EnvironmentSecretProvider().masking_secret()
    except MaskingSecretError as error:
        raise MissingSecretError("MASKING_SECRET is required for deterministic masking.") from error
    validate_secret(secret)
    return secret


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml_path(path)


def validate_masking_configuration(
    registry_path: Path = REGISTRY_PATH,
    rules_path: Path = MASKING_RULES_PATH,
    groups_path: Path = CONSISTENCY_GROUPS_PATH,
) -> dict[str, int]:
    registry = _load_yaml(registry_path)["columns"]
    rules = _load_yaml(rules_path)["rules"]
    groups = _load_yaml(groups_path)["groups"]
    registry_by_column = {
        f"{record['schema_name']}.{record['table_name']}.{record['column_name']}": record
        for record in registry
    }
    unknown_rules = sorted({record["masking_rule"] for record in registry} - set(rules))
    unknown_groups = sorted(
        {record["consistency_group"] for record in registry if record["consistency_group"]} - set(groups)
    )
    if unknown_rules or unknown_groups:
        raise InvalidConfigurationError(
            f"Registry references undefined masking configuration: rules={unknown_rules}; groups={unknown_groups}"
        )
    namespaces = [group["namespace"] for group in groups.values()]
    if len(namespaces) != len(set(namespaces)):
        raise InvalidConfigurationError("Consistency group namespaces must be unique.")

    configured_membership: dict[str, str] = {}
    for group_name, group in groups.items():
        for column in group["columns"]:
            if column not in registry_by_column:
                raise InvalidConfigurationError(
                    f"Consistency group {group_name} references an unknown registry column."
                )
            if column in configured_membership:
                raise InvalidConfigurationError(
                    "A registry column cannot belong to multiple consistency groups."
                )
            configured_membership[column] = group_name
            record = registry_by_column[column]
            if record["data_domain"] != group["data_domain"] or record["data_subject"] != group["data_subject"]:
                raise InvalidConfigurationError(
                    f"Consistency group {group_name} has an incompatible domain or subject."
                )
    expected_membership = {
        column: record["consistency_group"]
        for column, record in registry_by_column.items()
        if record["consistency_group"]
    }
    if configured_membership != expected_membership:
        raise InvalidConfigurationError(
            "Consistency group membership does not match the Privacy Metadata Registry."
        )

    for record in registry:
        if record["pii_category"] == "Non-PII" and record["masking_rule"] != "preserve_value":
            raise InvalidConfigurationError("Every Non-PII column must use preserve_value.")
        if record["pii_category"] == "Dubbio" and record["masking_rule"] != "review_before_masking":
            raise InvalidConfigurationError("Every Dubbio column must use review_before_masking.")
        if (
            record["pii_category"] == "PII-nascosta"
            and record["data_domain"] == "free_text_with_pii"
            and record["masking_rule"] != "redact_free_text"
        ):
            raise InvalidConfigurationError("Hidden PII in free text must use redact_free_text.")
    return {
        "registry_columns": len(registry),
        "masking_rules": len(rules),
        "consistency_groups": len(groups),
        "grouped_columns": len(configured_membership),
    }


SYNTHETIC_RULE_EXAMPLES = {
    "mask_person_name": "[REDACTED_NAME] → Persona_token",
    "mask_email": "u***@example.test → u_token@example.test",
    "mask_phone": "+39******001 → +39 000 0000001",
    "mask_tax_code": "ABCDEF********** → QWERTY00A01Z000R",
    "mask_iban": "IT************************* → ITxxX0000000000xxxxxxxxxxxx",
    "shift_birth_date": "1980-**-** → data entro ±30 giorni",
    "redact_free_text": "Contatto sintetico → [REDACTED_EMAIL]",
    "preserve_technical_key": "1001 → 1001",
    "preserve_value": "aggregato → aggregato",
    "review_before_masking": "valore ambiguo → esecuzione bloccata",
    "mask_contact_value": "contatto sintetico → formato email o telefono sintetico",
    "mask_postal_address": "[REDACTED_ADDRESS] → Indirizzo sintetico token",
}


def render_masking_documentation(
    rules_path: Path = MASKING_RULES_PATH,
    groups_path: Path = CONSISTENCY_GROUPS_PATH,
) -> str:
    rules = _load_yaml(rules_path)["rules"]
    groups = _load_yaml(groups_path)["groups"]
    lines = [
        "# Regole di masking", "",
        "> Documento generato deterministicamente dalle configurazioni YAML. Nessun secret è incluso.", "",
        "## Principi", "",
        "Le pseudonimizzazioni usano `HMAC-SHA-256(secret, namespace + ':' + valore_normalizzato)` e namespace distinti. I mapping di collisione esistono soltanto in memoria.", "",
        "## Consistency group", "",
        "| Gruppo | Dominio | Soggetto | Namespace | Normalizzazione | Formato | Colonne |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, group in groups.items():
        lines.append(
            f"| {name} | {group['data_domain']} | {group['data_subject']} | `{group['namespace']}` | "
            f"{group['normalization']} | {group['output_format']} | {', '.join(group['columns'])} |"
        )
    lines.extend(["", "## Regole", ""])
    for name, rule in rules.items():
        lines.extend([
            f"### `{name}`", "",
            f"- **Scopo e input:** domini `{', '.join(rule['domains'])}`; trasformazione `{rule['transformation_type']}`.",
            f"- **Normalizzazione:** `{rule['normalization']}`.",
            f"- **Algoritmo:** `{rule['algorithm']}`.",
            f"- **Output:** `{rule['output_format']}`; esempio sintetico: `{SYNTHETIC_RULE_EXAMPLES[name]}`.",
            f"- **Determinismo e namespace:** deterministico={str(rule['deterministic']).lower()}; il namespace è fornito dal consistency group o dal contesto del soggetto.",
            f"- **NULL e stringhe vuote:** `{rule['null_handling']}` / `{rule['empty_string_handling']}`.",
            f"- **Collisioni:** `{rule['collision_handling']}`.",
            f"- **Impatto analitico:** {rule['analytical_impact']}",
            f"- **Limiti:** {rule['limitations']}", "",
        ])
    lines.extend([
        "## Trasferimento concettuale verso Informatica", "",
        "Le configurazioni locali rappresentano concetti di dominio, regola e coerenza cross-tabella trasferibili a una piattaforma enterprise. Nomi, disponibilità e comportamento delle funzioni specifiche di Informatica Data Privacy Management dovranno essere verificati quando la licenza sarà disponibile; questo documento non attribuisce funzionalità non osservate.", "",
    ])
    return "\n".join(lines)


def write_masking_documentation(path: Path = DOCUMENTATION_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_masking_documentation(), encoding="utf-8")


def main() -> None:
    summary = validate_masking_configuration()
    write_masking_documentation()
    print(
        f"Masking configuration valid: {summary['registry_columns']} registry columns, "
        f"{summary['masking_rules']} rules, {summary['consistency_groups']} consistency groups."
    )
    print(f"Written: {DOCUMENTATION_PATH}")


if __name__ == "__main__":
    main()
