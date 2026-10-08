# Technical audit

**Audit date:** 2026-10-08

**Audited revision:** `6b199e153778af3e878026335575eabb52e9782d` (`main`)

**Environment:** macOS, Python 3.12.10 virtual environment, PostgreSQL 16 Alpine in Docker, database exposed locally on port 55433 because port 5433 was occupied by an unrelated container.

## Executive assessment

The repository contains a working, reproducible B2B privacy-governance proof of concept rather than a documentation-only concept. It generates deterministic synthetic CRM, HR and Billing data; discovers PostgreSQL metadata; profiles and classifies all 109 source columns; applies configured deterministic transformations; loads 20 masked tables transactionally; and validates counts, constraints, relationships, source immutability and checksums.

The audited run completed successfully with 2,063 source rows and 2,063 masked rows. The full suite passed 182 tests with 88.3% branch-aware coverage. Lint, formatting, type checks, repository-safety checks, schema drift and idempotence checks also passed. These results support controlled technical evaluation, but they do not make the solution production-ready or prove GDPR compliance.

## Implemented capabilities

- Three source schemas (`crm`, `hr`, `billing`) and three corresponding masked schemas.
- Twenty source tables created by ordered SQL initialization scripts.
- Seeded synthetic generation with a fixed reference date and test-only domains/numbers.
- Catalog discovery for tables, columns, keys, constraints and approved logical relationships.
- Aggregate profiling with pattern detection and redacted samples.
- A complete, versioned 109-column PII registry with classifications, evidence and review state.
- Twelve masking rules and nine cross-table consistency groups.
- HMAC-SHA-256-based deterministic pseudonymization, format-valid synthetic Italian tax codes and non-routable Italian IBANs, date shifting, address masking and free-text redaction.
- Transactional masked-schema replacement with rollback and idempotence tests.
- Referential-integrity, uniqueness, row-count, source-invariance and checksum validation.
- A CLI, Docker Compose workflow, CI, safety checks, dependency scanning and ignored generated artifacts.

## Findings

### High — confirmed defect, fixed: vulnerable development dependencies

`pip-audit` reported `PYSEC-2026-1845` for the repository-pinned `pytest==8.4.1`, with `9.0.3` as the fixed version. It also reported `PYSEC-2026-87` for `lxml==5.4.0`, resolved through the validation extra of `cyclonedx-bom==7.1.0`; that release constrained `lxml` below version 6. The pins were updated to `pytest==9.0.3`, `cyclonedx-bom==7.5.0` and `pip-audit==2.10.1`. The latter two upgrades permit CycloneDX Python 11 and `lxml==6.1.3`, above the advisory's fixed version, without a dependency conflict. The suite and dependency audit were rerun.

These packages belong to the development/test toolchain rather than runtime data transformation, but known vulnerable dependencies should not remain in a commercially credible repository. A clean virtual environment is required because upgrading a parent package does not necessarily remove obsolete transitive packages from a reused environment.

### Medium — confirmed documentation defect, fixed: stale test total

The README claimed 181 passing tests. The current suite collected and passed 182 tests against PostgreSQL. The claim was corrected and dated. Test totals should be treated as measured evidence, not a permanent product property.

### Medium — risk: regex-based free-text discovery and redaction

Free-text protection combines regular expressions and a known-name dictionary. Tests cover known email, phone, tax-code, IBAN, partial-card and reference patterns, but novel structures and contextual identifiers can remain undetected. The configured residual risk for `billing.pagamenti.riferimento_bancario` is accurate. Real data must not be processed without stronger discovery, sampling controls and human review.

### Medium — risk: local environment secrets and database privileges

The local `.env` is ignored and was not printed or tracked. Compose uses a single application/database user suitable for a local demonstration, but it does not implement production-grade least privilege, secret rotation, managed key storage or separation between source-reader and masked-writer roles. Production deployment remains out of scope.

### Medium — risk: pseudonymization is reversible by linkage or secret compromise

HMAC prevents direct dictionary checking without the secret and namespaces reduce unintended cross-domain correlation. It is still pseudonymization, not anonymization: equality is intentionally retained within consistency groups, auxiliary information may enable linkage, and compromise of the secret enables recomputation. No re-identification mapping is stored.

### Low — architectural debt: compatibility facades remain

The modular layers are enforced by contract tests, while several mature workflows remain in top-level compatibility modules and are injected into application services. This is documented incremental migration debt, not a correctness defect. Moving them behind repository ports should be prioritized only when it reduces product maintenance or enables a required deployment model.

### Low — operational limitation: initialization is first-volume only

PostgreSQL runs `docker-entrypoint-initdb.d` scripts only when its data volume is new. The README states this correctly and the clean-environment script makes destructive reset explicit. Pilot operators must understand this lifecycle and use an approved reset procedure.

## Security review

- No tracked `.env`, private key, certificate, dump or generated output was found by the repository safety check (151 tracked files inspected).
- Database values are parameterized. Dynamic identifiers use `psycopg.sql.Identifier`; generated statement fragments come from validated/catalog metadata rather than user values.
- Normal CLI errors redact connection details and avoid printing secrets, source records, mapping tables or pseudonyms.
- Generated reports contain aggregate metrics, redacted samples and checksums. `output/` is ignored.
- Masked schema replacement uses `DROP SCHEMA ... CASCADE`, but only for validated `masked_*` targets and within the deliberate masking transaction. Source schemas are checked before and after execution.
- No evidence of an Informatica integration exists; documentation correctly describes only conceptual transfer.

## Test classification and reproducibility

The 182-test result mixes pure unit/contract tests and PostgreSQL integration tests. Database-dependent tests exercise real PostgreSQL behavior; they are not mocked. A database-free attempt produced 130 passes plus expected database failures/errors and therefore must not be presented as a successful suite.

Verified commands:

```bash
POSTGRES_PORT=55433 docker compose up -d --wait postgres
POSTGRES_PORT=55433 .venv/bin/python -m pytest -q
POSTGRES_PORT=55433 .venv/bin/python -m src.cli all
POSTGRES_PORT=55433 .venv/bin/python -m src.cli drift --check
POSTGRES_PORT=55433 .venv/bin/python -m src.cli validate --check-idempotence
.venv/bin/python -m mypy src
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/check_repository_safety.py
git diff --check
```

## Acceptance gates

| Gate | Result | Evidence |
|---|---|---|
| Reproducible execution path | Pass | Compose, CLI and clean-environment script |
| Core functionality | Pass | End-to-end run and database integration tests |
| Known critical defects | Pass | None found |
| Honest test outcomes | Pass | Dated 182-test result and environment recorded |
| Relational integrity | Pass | Constraint and declared/logical relationship validations |
| Sensitive output handling | Pass for synthetic demo | Safety tests and aggregate-only reports |
| README/code alignment | Pass after correction | Test count corrected; capabilities reproduced |
| Production readiness | Not claimed | IAM, KMS, legal review and scale testing absent |

## Priorities before a controlled pilot

The synthetic proof-of-concept gate is complete for the audited environment. Before a controlled pilot, the product requires authentication, least-privilege authorization, managed keys, operational audit export, monitoring, supported deployment packaging, licensing decisions, support ownership, and validation on an authorized representative dataset. Detailed priorities are maintained in [commercial readiness](commercial_readiness.md).
