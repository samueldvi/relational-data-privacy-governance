"""Generate human-readable classification documentation from the registry."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


DOCUMENT_PATH = Path("docs/CLASSIFICAZIONE_PII.md")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    def clean(value: Any) -> str:
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")

    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend("| " + " | ".join(clean(value) for value in row) + " |" for row in rows)
    return "\n".join(output)


def render_classification_markdown(records: list[dict[str, Any]]) -> str:
    category_counts = Counter(record["pii_category"] for record in records)
    schema_counts = Counter(record["schema_name"] for record in records)
    review_counts = Counter(record["review_status"] for record in records)
    doubtful = [record for record in records if record["pii_category"] == "Dubbio"]
    false_positives = [record for record in records if record["review_status"] == "false_positive_confirmed"]
    hidden = [record for record in records if record["pii_category"] == "PII-nascosta"]
    relevant_relationships = [
        record for record in records
        if record["declared_relationship"] or record["logical_relationship"]
    ]

    sections = [
        "# Classificazione PII",
        "",
        "> Documento generato deterministicamente da `config/pii_registry.yml`. "
        "Il registry strutturato è la fonte primaria.",
        "",
        "## Sintesi generale",
        "",
        f"Colonne classificate: **{len(records)}**. Nessuna colonna è esclusa dalla copertura.",
        "",
        _table(
            ["Categoria", "Colonne"],
            [[category, category_counts[category]] for category in sorted(category_counts)],
        ),
        "",
        "### Copertura per schema",
        "",
        _table(["Schema", "Colonne"], [[schema, schema_counts[schema]] for schema in sorted(schema_counts)]),
        "",
        "### Stato della revisione",
        "",
        _table(["Stato", "Colonne"], [[status, review_counts[status]] for status in sorted(review_counts)]),
        "",
        "## Colonne Dubbio",
        "",
        _table(
            ["Colonna", "Dominio", "Confidence", "Motivazione", "Revisione richiesta"],
            [[
                f"{r['schema_name']}.{r['table_name']}.{r['column_name']}", r["data_domain"],
                f"{r['confidence']:.2f}", r["rationale"], r["review_note"],
            ] for r in doubtful],
        ) if doubtful else "Nessuna colonna classificata come Dubbio.",
        "",
        "## Falsi positivi confermati",
        "",
        _table(
            ["Colonna", "Dominio", "Motivazione"],
            [[f"{r['schema_name']}.{r['table_name']}.{r['column_name']}", r["data_domain"], r["rationale"]]
             for r in false_positives],
        ) if false_positives else "Nessun falso positivo confermato.",
        "",
        "## PII nascoste",
        "",
        _table(
            ["Colonna", "Dominio", "Soggetto", "Regola prevista", "Stato"],
            [[
                f"{r['schema_name']}.{r['table_name']}.{r['column_name']}", r["data_domain"],
                r["data_subject"], r["masking_rule"], r["review_status"],
            ] for r in hidden],
        ),
        "",
        "## Relazioni rilevanti",
        "",
        _table(
            ["Colonna", "Relazione dichiarata", "Relazione logica"],
            [[
                f"{r['schema_name']}.{r['table_name']}.{r['column_name']}",
                ", ".join(item["target"] for item in r["declared_relationship"]) or "—",
                ", ".join(f"{item['target']} ({item['status']})" for item in r["logical_relationship"]) or "—",
            ] for r in relevant_relationships],
        ),
        "",
        "## Catalogo completo",
        "",
        _table(
            [
                "Schema", "Tabella", "Colonna", "Categoria", "Dominio", "Soggetto",
                "Confidence", "Masking rule", "Consistency group", "Revisione", "Motivazione",
            ],
            [[
                r["schema_name"], r["table_name"], r["column_name"], r["pii_category"],
                r["data_domain"], r["data_subject"], f"{r['confidence']:.2f}",
                r["masking_rule"], r["consistency_group"], r["review_status"], r["rationale"],
            ] for r in records],
        ),
        "",
        "## Limiti",
        "",
        "- La classificazione usa metadati, profiling sintetico, relazioni e regole contestuali; non sostituisce la conoscenza del data owner.",
        "- Regex e confronto con nomi noti non garantiscono copertura completa della PII non strutturata.",
        "- Le relazioni `logical_suspected` restano ipotesi e non vengono promosse automaticamente.",
        "- Le masking rule sono proposte di governance e non sono ancora implementate.",
        "",
        "## Responsabilità della revisione umana",
        "",
        "Il data owner deve validare le colonne `Dubbio`, le relazioni sospette, il contesto degli identificativi e l'impatto analitico delle trasformazioni prima dell'uso in produzione.",
        "",
    ]
    return "\n".join(sections)


def write_classification_markdown(
    records: list[dict[str, Any]], path: Path = DOCUMENT_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_classification_markdown(records), encoding="utf-8")
