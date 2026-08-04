"""Build and validate the deterministic Privacy Metadata Registry."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from src.generate_docs import write_classification_markdown
from src.inventory import generate_inventory
from src.profile_columns import generate_profiling


INVENTORY_PATH = Path("output/inventory.csv")
PROFILING_PATH = Path("output/profiling_results.json")
RELATIONSHIPS_PATH = Path("output/logical_relationships.csv")
DOMAINS_PATH = Path("config/data_domains.yml")
OVERRIDES_PATH = Path("config/classification_overrides.yml")
REGISTRY_PATH = Path("config/pii_registry.yml")
CATALOG_PATH = Path("output/pii_catalog.csv")

ALLOWED_CATEGORIES = {"PII-diretta", "PII-indiretta", "PII-nascosta", "Non-PII", "Dubbio"}
ALLOWED_REVIEW_STATUSES = {"auto_proposed", "review_required", "confirmed", "false_positive_confirmed"}
ALLOWED_SUBJECTS = {
    "customer", "employee", "commercial_contact", "external_person",
    "bank_account_holder", "mixed", "not_applicable", "unknown",
}

REQUIRED_FIELDS = {
    "schema_name", "table_name", "column_name", "data_type", "nullable",
    "is_primary_key", "is_foreign_key", "is_unique", "declared_relationship",
    "logical_relationship", "pii_category", "data_domain", "data_subject",
    "confidence", "detection_methods", "evidence", "rationale", "masking_rule",
    "consistency_group", "review_status", "review_note", "dependencies",
}

CATALOG_FIELDS = (
    "schema_name", "table_name", "column_name", "ordinal_position", "data_type",
    "nullable", "is_primary_key", "is_foreign_key", "is_unique",
    "declared_relationship", "logical_relationship", "pii_category", "data_domain",
    "data_subject", "confidence", "detection_methods", "evidence", "rationale",
    "masking_rule", "consistency_group", "review_status", "review_note", "dependencies",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as input_file:
        return yaml.safe_load(input_file)


def _load_inputs() -> tuple[list[dict[str, str]], dict[tuple[str, str, str], dict[str, Any]], list[dict[str, str]]]:
    if not INVENTORY_PATH.exists() or not RELATIONSHIPS_PATH.exists():
        generate_inventory()
    if not PROFILING_PATH.exists():
        generate_profiling()
    with INVENTORY_PATH.open(encoding="utf-8", newline="") as input_file:
        inventory = list(csv.DictReader(input_file))
    with PROFILING_PATH.open(encoding="utf-8") as input_file:
        profiling_document = json.load(input_file)
    profiling = {
        (row["schema_name"], row["table_name"], row["column_name"]): row
        for row in profiling_document["columns"]
    }
    with RELATIONSHIPS_PATH.open(encoding="utf-8", newline="") as input_file:
        relationships = list(csv.DictReader(input_file))
    return inventory, profiling, relationships


def _subject(schema: str, table: str, column: str) -> str:
    if schema == "crm":
        if table == "referenti_commerciali":
            return "commercial_contact"
        if table == "campagne":
            return "not_applicable"
        return "customer"
    if schema == "hr":
        if table == "formazione":
            return "external_person" if column == "docente" else "not_applicable"
        if table == "reparti" and column != "responsabile_id":
            return "not_applicable"
        return "employee"
    if schema == "billing":
        if table == "report_mensili":
            return "not_applicable"
        if table == "coordinate_bancarie" and column in {"iban", "intestatario"}:
            return "bank_account_holder"
        return "customer"
    return "unknown"


def _identifier_classification(schema: str, table: str, column: str) -> dict[str, Any]:
    non_personal = {
        ("crm", "campagne"), ("hr", "formazione"), ("hr", "reparti"),
        ("billing", "report_mensili"),
    }
    if (schema, table) in non_personal and column != "responsabile_id":
        return {
            "pii_category": "Non-PII", "data_domain": "internal_identifier",
            "data_subject": "not_applicable", "confidence": 0.94,
            "rationale": "Chiave tecnica della struttura operativa, priva di collegamento diretto a una persona nel modello corrente.",
        }
    return {
        "pii_category": "PII-indiretta", "data_domain": "internal_identifier",
        "data_subject": _subject(schema, table, column), "confidence": 0.93,
        "rationale": "Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento.",
    }


def _context_classification(schema: str, table: str, column: str) -> dict[str, Any]:
    subject = _subject(schema, table, column)
    if schema == "crm" and table == "campagne":
        return {"pii_category": "Non-PII", "data_domain": "business_metadata", "data_subject": "not_applicable", "confidence": 0.94,
                "rationale": "Metadato di campagna sintetica non riferito a un interessato individuale."}
    if schema == "crm" and table == "clienti":
        domain = "technical_timestamp" if column == "data_registrazione" else "business_metadata"
        return {"pii_category": "PII-indiretta", "data_domain": domain, "data_subject": subject, "confidence": 0.82,
                "rationale": "Attributo del profilo cliente che può contribuire alla segmentazione o correlazione quando unito all'identificativo."}
    if schema == "crm" and table == "consensi":
        return {"pii_category": "PII-indiretta", "data_domain": "consent_information", "data_subject": subject, "confidence": 0.94,
                "rationale": "Informazione di consenso associata tramite chiave a un cliente e quindi parte del suo profilo privacy."}
    if schema == "crm" and table == "contatti_extra" and column == "tipo":
        return {"pii_category": "Non-PII", "data_domain": "business_metadata", "data_subject": subject, "confidence": 0.90,
                "rationale": "Discriminante del tipo di contatto; non contiene da solo il valore personale."}
    if schema == "crm" and table == "note_cliente":
        return {"pii_category": "PII-indiretta", "data_domain": "technical_timestamp", "data_subject": subject, "confidence": 0.90,
                "rationale": "Timestamp della nota collegata a un cliente tramite foreign key."}
    if schema == "crm" and table == "ordini":
        return {"pii_category": "PII-indiretta", "data_domain": "financial_transaction", "data_subject": subject, "confidence": 0.90,
                "rationale": "Attributo economico o operativo dell'ordine collegato a un cliente."}
    if schema == "billing" and table == "coordinate_bancarie" and column == "banca":
        return {"pii_category": "Non-PII", "data_domain": "business_metadata", "data_subject": "not_applicable", "confidence": 0.91,
                "rationale": "Denominazione sintetica dell'istituto, non dell'intestatario del conto."}
    if schema == "billing" and table == "report_mensili":
        return {"pii_category": "Non-PII", "data_domain": "aggregate_metric", "data_subject": "not_applicable", "confidence": 0.99,
                "rationale": "Metrica mensile aggregata senza dettaglio individuale nel modello corrente."}
    if schema == "billing" and table == "fatture" and column == "iva":
        return {"pii_category": "Non-PII", "data_domain": "financial_transaction", "data_subject": "not_applicable", "confidence": 0.90,
                "rationale": "Aliquota fiscale isolata, non identificante e comune a molte fatture."}
    if schema == "billing" and table in {"fatture", "pagamenti", "sconti", "solleciti"}:
        return {"pii_category": "PII-indiretta", "data_domain": "financial_transaction", "data_subject": subject, "confidence": 0.88,
                "rationale": "Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente."}
    if schema == "hr" and table in {"dipendenti", "buste_paga", "presenze", "valutazioni"}:
        return {"pii_category": "PII-indiretta", "data_domain": "employment_information", "data_subject": subject, "confidence": 0.92,
                "rationale": "Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente."}
    if schema == "hr" and table == "formazione":
        return {"pii_category": "Non-PII", "data_domain": "business_metadata", "data_subject": "not_applicable", "confidence": 0.92,
                "rationale": "Metadato del corso sintetico non riferito a una persona, escluso il docente trattato separatamente."}
    if schema == "hr" and table == "reparti":
        return {"pii_category": "Non-PII", "data_domain": "business_metadata", "data_subject": "not_applicable", "confidence": 0.95,
                "rationale": "Metadato organizzativo del reparto privo di riferimento individuale."}
    return {"pii_category": "Dubbio", "data_domain": "business_metadata", "data_subject": subject, "confidence": 0.35,
            "rationale": "Metadati e profiling non consentono una decisione affidabile; serve validazione semantica del data owner."}


def _base_classification(inventory: dict[str, str], profile: dict[str, Any]) -> dict[str, Any]:
    schema, table, column = inventory["schema_name"], inventory["table_name"], inventory["column_name"]
    patterns = set(profile["detected_patterns"])
    subject = _subject(schema, table, column)
    if (schema, table, column) == ("billing", "pagamenti", "riferimento_bancario"):
        return {"pii_category": "Dubbio", "data_domain": "bank_reference", "data_subject": "customer", "confidence": 0.45,
                "rationale": "Il campo contiene riferimenti sintetici eterogenei e una quota di valori compatibili con codici fiscali; il data owner deve chiarire la semantica produttiva."}
    if (schema, table, column) == ("crm", "contatti_extra", "valore"):
        return {"pii_category": "PII-diretta", "data_domain": "contact_value", "data_subject": "customer", "confidence": 0.98,
                "rationale": "Il discriminante di riga e il profiling mostrano valori email o telefono direttamente utilizzabili per contattare il cliente."}
    if "free_text_pii" in patterns:
        return {"pii_category": "PII-nascosta", "data_domain": "free_text_with_pii", "data_subject": subject, "confidence": 0.99,
                "rationale": "Il testo libero contiene pattern PII e nomi noti; richiede futura redaction multipattern e revisione dei limiti regex."}
    if "italian_tax_code" in patterns:
        return {"pii_category": "PII-diretta", "data_domain": "italian_tax_code", "data_subject": subject, "confidence": 0.99,
                "rationale": "Struttura di 16 caratteri e carattere di controllo validi, confermati dal profiling dei valori."}
    if "italian_iban" in patterns:
        return {"pii_category": "PII-diretta", "data_domain": "italian_iban", "data_subject": subject, "confidence": 0.99,
                "rationale": "Valori con struttura italiana e checksum IBAN valido, associati a conto o intestatario."}
    if "email" in patterns:
        return {"pii_category": "PII-diretta", "data_domain": "email_address", "data_subject": subject, "confidence": 0.98,
                "rationale": "Sintassi email rilevata sui valori e normalizzazione case-insensitive disponibile per i confronti."}
    if "phone" in patterns:
        return {"pii_category": "PII-diretta", "data_domain": "phone_number", "data_subject": subject, "confidence": 0.98,
                "rationale": "Struttura telefonica coerente rilevata nei valori, non soltanto nel nome della colonna."}
    if "birth_date" in patterns:
        return {"pii_category": "PII-indiretta", "data_domain": "birth_date", "data_subject": subject, "confidence": 0.99,
                "rationale": "Data di nascita plausibile e contestualmente riferita al cliente, utilizzabile come quasi-identificatore."}
    if "person_name" in patterns or "surname" in patterns:
        return {"pii_category": "PII-diretta", "data_domain": "person_name", "data_subject": subject, "confidence": 0.97,
                "rationale": "Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone."}
    if "postal_address" in patterns:
        if column == "via":
            return {"pii_category": "PII-diretta", "data_domain": "postal_address", "data_subject": subject, "confidence": 0.95,
                    "rationale": "Componente granulare dell'indirizzo postale collegata tramite foreign key a un cliente."}
        return {"pii_category": "PII-indiretta", "data_domain": "geographic_information", "data_subject": subject, "confidence": 0.88,
                "rationale": "Componente geografica collegata a un cliente, utile alla re-identificazione in combinazione con altri attributi."}
    if "postal_code" in patterns:
        return {"pii_category": "PII-indiretta", "data_domain": "geographic_information", "data_subject": subject, "confidence": 0.90,
                "rationale": "CAP formalmente coerente e collegato all'indirizzo del cliente; costituisce un quasi-identificatore geografico."}
    if "technical_identifier" in patterns:
        return _identifier_classification(schema, table, column)
    return _context_classification(schema, table, column)


def _masking_rule(record: dict[str, Any], domains: dict[str, Any]) -> str:
    if record["pii_category"] == "Dubbio":
        return "review_before_masking"
    if record["pii_category"] == "Non-PII":
        return "preserve_value"
    if record["data_domain"] == "internal_identifier":
        return "preserve_technical_key"
    return domains[record["data_domain"]]["planned_transformation"]


def _consistency_group(record: dict[str, Any]) -> str | None:
    domain, subject = record["data_domain"], record["data_subject"]
    key = f"{record['schema_name']}.{record['table_name']}.{record['column_name']}"
    if domain == "italian_tax_code":
        return "employee_tax_code" if subject == "employee" else "customer_tax_code"
    if domain == "italian_iban":
        return "employee_iban" if subject == "employee" else "customer_iban"
    if domain == "email_address":
        if subject == "employee":
            return "employee_email"
        if subject == "commercial_contact":
            return "commercial_contact_email"
        return "customer_email"
    if domain == "phone_number":
        return "commercial_contact_phone" if subject == "commercial_contact" else "customer_phone"
    if domain == "contact_value" or key.endswith("riferimento_bancario"):
        return None
    return None


def _relationship_indexes(relationships: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    declared: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    logical: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for relation in relationships:
        key = (relation["source_schema"], relation["source_table"], relation["source_column"])
        item = {
            "target": f"{relation['target_schema']}.{relation['target_table']}.{relation['target_column']}",
            "status": relation["relationship_status"],
            "match_percentage": float(relation["match_percentage"]),
            "orphan_count": int(relation["orphan_count"]),
        }
        (declared if relation["relationship_status"] == "declared" else logical)[key].append(item)
    for index in (declared, logical):
        for values in index.values():
            values.sort(key=lambda item: (item["target"], item["status"]))
    return declared, logical


def build_registry_records(
    inventory: list[dict[str, str]], profiling: dict[tuple[str, str, str], dict[str, Any]],
    relationships: list[dict[str, str]], domains: dict[str, Any], overrides: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    declared_index, logical_index = _relationship_indexes(relationships)
    records = []
    for column in inventory:
        key_tuple = (column["schema_name"], column["table_name"], column["column_name"])
        key = ".".join(key_tuple)
        profile = profiling[key_tuple]
        proposal = _base_classification(column, profile)
        detection_methods = ["column_context", "technical_metadata"]
        if profile["detected_patterns"]:
            detection_methods.append("value_profiling")
        if profile["cross_table_matches"]:
            detection_methods.append("cross_table_comparison")
        if declared_index[key_tuple] or logical_index[key_tuple]:
            detection_methods.append("relationship_analysis")
        review_status = "review_required" if proposal["pii_category"] == "Dubbio" else "auto_proposed"
        override = overrides.get(key)
        if override:
            proposal.update({
                "pii_category": override["classification"], "data_domain": override["domain"],
                "data_subject": override["subject"], "confidence": float(override["confidence"]),
                "rationale": override["rationale"],
            })
            review_status = override["review_status"]
            detection_methods.append("manual_override")

        dependencies = sorted({
            item["target"] for item in declared_index[key_tuple] + logical_index[key_tuple]
        } | {
            item["target_column"] for item in profile["cross_table_matches"]
        })
        evidence = [
            f"row_count={profile['row_count']}; non_null={profile['non_null_count']}; distinct={profile['distinct_count']}"
        ]
        if profile["detected_patterns"]:
            evidence.append("pattern=" + ",".join(profile["detected_patterns"]))
        for match in profile["cross_table_matches"]:
            if match["match_percentage"] >= 80:
                evidence.append(
                    f"cross_match={match['target_column']}:{match['match_percentage']:.2f}%"
                )

        record = {
            "schema_name": column["schema_name"], "table_name": column["table_name"],
            "column_name": column["column_name"], "ordinal_position": int(column["ordinal_position"]),
            "data_type": column["data_type"], "nullable": column["is_nullable"] == "YES",
            "is_primary_key": column["is_primary_key"] == "true",
            "is_foreign_key": column["is_foreign_key"] == "true",
            "is_unique": column["is_unique"] == "true",
            "declared_relationship": declared_index[key_tuple],
            "logical_relationship": logical_index[key_tuple],
            **proposal,
            "confidence": round(float(proposal["confidence"]), 2),
            "detection_methods": sorted(set(detection_methods)), "evidence": evidence,
            "masking_rule": None, "consistency_group": None,
            "review_status": review_status,
            "review_note": (
                f"Decisione applicata da {override['source']}." if override
                else "Validazione del data owner obbligatoria prima del masking." if review_status == "review_required"
                else "Proposta automatica da sottoporre al normale ciclo di governance."
            ),
            "dependencies": dependencies,
        }
        record["masking_rule"] = _masking_rule(record, domains)
        record["consistency_group"] = _consistency_group(record)
        records.append(record)
    return records


def validate_registry(records: list[dict[str, Any]], expected_columns: set[tuple[str, str, str]], domains: dict[str, Any]) -> None:
    actual_columns = {(r.get("schema_name"), r.get("table_name"), r.get("column_name")) for r in records}
    if actual_columns != expected_columns or len(records) != len(expected_columns):
        missing = sorted(expected_columns - actual_columns)
        extra = sorted(actual_columns - expected_columns)
        raise ValueError(f"Registry coverage mismatch: missing={missing}; extra={extra}")
    for record in records:
        missing_fields = REQUIRED_FIELDS - set(record)
        if missing_fields:
            raise ValueError(f"Incomplete registry record for {record.get('column_name')}: {sorted(missing_fields)}")
        if record["pii_category"] not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid PII category for {record['column_name']}")
        if record["review_status"] not in ALLOWED_REVIEW_STATUSES:
            raise ValueError(f"Invalid review status for {record['column_name']}")
        if record["data_subject"] not in ALLOWED_SUBJECTS:
            raise ValueError(f"Invalid data subject for {record['column_name']}")
        if record["data_domain"] not in domains:
            raise ValueError(f"Undefined data domain for {record['column_name']}")
        if not 0 <= record["confidence"] <= 1:
            raise ValueError(f"Invalid confidence for {record['column_name']}")
        for field in ("pii_category", "data_domain", "data_subject", "rationale", "review_status", "review_note"):
            if record[field] in (None, ""):
                raise ValueError(f"Missing {field} for {record['column_name']}")
        if record["masking_rule"] is None:
            raise ValueError(f"Missing masking rule for {record['column_name']}")


def _write_registry(records: list[dict[str, Any]]) -> None:
    document = {
        "version": 1,
        "source": {
            "inventory": str(INVENTORY_PATH), "profiling": str(PROFILING_PATH),
            "overrides": str(OVERRIDES_PATH), "dynamic_timestamp_included": False,
        },
        "columns": records,
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8"
    )


def _write_catalog(records: list[dict[str, Any]]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG_PATH.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CATALOG_FIELDS, lineterminator="\n")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for field in ("declared_relationship", "logical_relationship", "detection_methods", "evidence", "dependencies"):
                row[field] = json.dumps(row[field], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            writer.writerow({field: row.get(field) for field in CATALOG_FIELDS})


def generate_classification() -> list[dict[str, Any]]:
    inventory, profiling, relationships = _load_inputs()
    domain_document = _load_yaml(DOMAINS_PATH)
    domains = domain_document["domains"]
    override_document = _load_yaml(OVERRIDES_PATH)
    overrides = {item["column"]: item for item in override_document["overrides"]}
    records = build_registry_records(inventory, profiling, relationships, domains, overrides)
    expected = {(r["schema_name"], r["table_name"], r["column_name"]) for r in inventory}
    validate_registry(records, expected, domains)
    _write_registry(records)
    _write_catalog(records)
    write_classification_markdown(records)
    return records


def main() -> None:
    records = generate_classification()
    categories = Counter(record["pii_category"] for record in records)
    statuses = Counter(record["review_status"] for record in records)
    print(f"Privacy Metadata Registry generated for {len(records)} columns.")
    print("Categories: " + ", ".join(f"{key}={categories[key]}" for key in sorted(categories)))
    print("Review: " + ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses)))
    print(f"Written: {REGISTRY_PATH}, {CATALOG_PATH}, docs/CLASSIFICAZIONE_PII.md")


if __name__ == "__main__":
    main()
