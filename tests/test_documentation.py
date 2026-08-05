from __future__ import annotations

import re
from pathlib import Path

README = Path("README.md").read_text(encoding="utf-8")
INFORMATICA = Path("docs/TRASFERIMENTO_INFORMATICA.md").read_text(encoding="utf-8")
WEB_DEMO = Path("docs/WEB_DEMO_FEASIBILITY.md").read_text(encoding="utf-8")


def test_readme_has_real_ci_badge_and_tldr_near_the_title() -> None:
    assert README.startswith("# Relational Data Privacy Governance\n")
    assert "actions/workflows/ci.yml/badge.svg" in README
    assert README.index("## TL;DR") < README.index("## Risultati verificabili")


def test_readme_documents_architecture_quick_start_cli_security_and_limits() -> None:
    for required in (
        "## Architettura",
        "## Quick start",
        "## CLI",
        "## Sicurezza e governance",
        "## Limiti",
        "python -m src.cli all",
        "python -m src.cli status",
        "scripts/check_repository_safety.py",
        "scripts/validate_clean_environment.sh",
    ):
        assert required in README
    assert "Synthetic Data" in README and "Privacy Metadata Registry" in README
    test_count = re.search(r"\| Test automatici \| (\d+) superati", README)
    assert test_count and int(test_count.group(1)) >= 159
    assert "docs/ARCHITECTURE.md" in README


def test_readme_is_explicit_about_synthetic_data_and_informatica_scope() -> None:
    normalized = " ".join(README.split())
    assert "interamente sintetico" in README
    assert "non la prova che il repository utilizzi Informatica direttamente" in normalized
    assert "Named Entity Recognition" in README
    assert "rischio residuo" in README


def test_informatica_document_distinguishes_three_levels_and_has_mapping() -> None:
    for required in (
        "## Implementato localmente",
        "## Trasferibile concettualmente",
        "## Da verificare sulla piattaforma",
        "## Tabella di mapping",
        "## Piano di adozione",
        "## Domande da porre al cliente",
    ):
        assert required in INFORMATICA
    assert "nomi esatti" in INFORMATICA and "limiti di licenza" in INFORMATICA
    assert "| Concetto locale |" in INFORMATICA


def test_web_demo_assesses_options_and_recommends_static_site() -> None:
    for option in ("Streamlit", "FastAPI + frontend leggero", "Sito statico", "GitHub Pages"):
        assert option in WEB_DEMO
    assert "si raccomanda un **sito statico**" in WEB_DEMO
    assert "mai connettersi al database" in WEB_DEMO
    assert "## Roadmap" in WEB_DEMO
