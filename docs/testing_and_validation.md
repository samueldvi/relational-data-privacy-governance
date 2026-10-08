# Testing and validation

## Test layers

- Pure unit tests cover domain models, normalization, privacy primitives, collision behavior and application orchestration.
- Contract tests enforce module dependency boundaries and public CLI structure.
- PostgreSQL integration tests cover data generation, metadata discovery, profiling, classification, transactional masking, rollback, constraints, relationships and schema drift.
- Repository tests inspect CI, container hardening, dependency/supply-chain configuration, documentation and sensitive-file controls.

Database integration tests require PostgreSQL; they are not silently skipped. A run without a reachable database is a blocked integration run, not a failed product result and not a passing suite.

## Clean verification sequence

```bash
cp .env.example .env
# Replace placeholders with local-only values.
python3.12 -m venv .venv
.venv/bin/python -m pip install --requirement requirements-dev.txt
docker compose up -d --wait postgres
.venv/bin/python -m src.cli all
.venv/bin/python -m src.cli drift --check
.venv/bin/python -m src.cli validate --check-idempotence
.venv/bin/python -m coverage run -m pytest -q
.venv/bin/python -m coverage report
.venv/bin/python -m mypy src
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/check_repository_safety.py
git diff --check
```

If the configured host port is already occupied, choose an unused one consistently:

```bash
POSTGRES_PORT=55433 docker compose up -d --wait postgres
POSTGRES_PORT=55433 .venv/bin/python -m src.cli all
POSTGRES_PORT=55433 .venv/bin/python -m pytest -q
```

## Verified result (2026-10-08)

| Check | Result |
|---|---:|
| Tests | 182 passed |
| Branch-aware coverage | 88.3% (gate 87%) |
| Ruff lint | passed |
| Ruff formatting | 122 files formatted |
| Mypy | 83 source files, no issues |
| Safety scan | 151 tracked files, 0 violations |
| End-to-end rows | 2,063 source / 2,063 masked |
| Classified columns | 109 |
| Masked tables | 20 |
| Pipeline validations | 14 |
| Schema drift | 0 breaking, 0 non-breaking, 0 governance |
| Idempotence | verified |

The end-to-end global checksum was `9d45e46e11c7389a6df811be2768cefc116b54752b24ce75c97c097684e3b2fd` at audited commit `6b199e1`. A commit change can alter manifest metadata, so table checksums are the better comparison for unchanged protected data.

Generated outputs are ignored and reproducible. A demonstration transcript should record the date, commit, Python/PostgreSQL versions, exact commands and exit status without copying `.env` or source rows.
