from __future__ import annotations

import re
from pathlib import Path

README = Path("README.md").read_text(encoding="utf-8")
INFORMATICA = Path("docs/TRASFERIMENTO_INFORMATICA.md").read_text(encoding="utf-8")
WEB_DEMO = Path("docs/WEB_DEMO_FEASIBILITY.md").read_text(encoding="utf-8")
WHITEPAPER = Path("docs/technical_whitepaper.md").read_text(encoding="utf-8")
COMMERCIAL_READINESS = Path("docs/commercial_readiness.md").read_text(encoding="utf-8")


def test_readme_has_real_ci_badge_and_positioning_near_the_title() -> None:
    assert README.startswith("# Relational Data Privacy Governance\n")
    assert "actions/workflows/ci.yml/badge.svg" in README
    assert README.index("validated B2B proof of concept") < README.index("## Business value")


def test_readme_documents_product_scope_architecture_operation_and_security() -> None:
    for required in (
        "## Business value",
        "## Verified reference implementation",
        "## Architecture",
        "## Quick start",
        "## Command-line interface",
        "## Security and governance boundaries",
        "## Product maturity",
        "python -m src.cli all",
        "python -m src.cli status",
        "scripts/check_repository_safety.py",
        "scripts/validate_clean_environment.sh",
    ):
        assert required in README
    test_count = re.search(r"\| Automated tests \| (\d+) passed", README)
    assert test_count and int(test_count.group(1)) >= 159
    assert "docs/ARCHITECTURE.md" in README


def test_readme_is_explicit_about_synthetic_data_and_product_limits() -> None:
    normalized = " ".join(README.split())
    assert "synthetic" in README.lower()
    assert "No direct Informatica Data Privacy Management integration" in normalized
    assert "not yet suitable for production workloads" in normalized
    assert "This is pseudonymization, not anonymization" in normalized
    assert_public_product_documents_are_commercially_scoped_and_non_academic()
    assert_whitepaper_and_commercial_readiness_cover_product_evaluation_needs()


def assert_public_product_documents_are_commercially_scoped_and_non_academic() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (Path("README.md"), *Path("docs").glob("*.md"))
    ).lower()
    for forbidden in ("steve jobs academy", "spindox", "tirocinio", "project work its", "esame"):
        assert forbidden not in combined
    assert "validated b2b proof of concept" in README.lower()
    assert "not currently a production product" in COMMERCIAL_READINESS.lower()


def assert_whitepaper_and_commercial_readiness_cover_product_evaluation_needs() -> None:
    for required in (
        "## Executive summary",
        "## Business problem and customer needs",
        "## Proposed solution and value proposition",
        "## Architecture and technology stack",
        "## Data discovery and PII classification",
        "## Masking and pseudonymization",
        "## Referential-integrity preservation",
        "## Technical implementation",
        "## Reproducible validation results",
        "## Security architecture and limitations",
        "## Deployment considerations",
        "## Business use cases",
        "## Product roadmap",
    ):
        assert required in WHITEPAPER
    for gap in (
        "Authentication",
        "Authorization",
        "Secret management",
        "Monitoring",
        "Licensing/IP",
        "Support",
        "Real-world validation",
    ):
        assert gap in COMMERCIAL_READINESS


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
