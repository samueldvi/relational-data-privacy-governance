# Data governance workflow

## 1. Synthetic generation

The generator builds all rows from an explicit seed and fixed reference date before opening the load transaction. Reserved test domains and deliberately synthetic telephone/bank structures reduce the chance of representing real people. The generator resets data, not schemas.

## 2. Discovery and inventory

PostgreSQL catalog queries enumerate the three approved source schemas, tables, ordered columns, types, nullability, keys, unique constraints and foreign keys. Additional approved logical relationships capture cross-table equality that is not represented by a database foreign key. Missing or unexpected structure is surfaced by schema-drift checks.

## 3. Profiling

Profiling calculates row/null/distinct counts, lengths and known-pattern matches. Samples are limited and redacted before JSON serialization. Empty tables and null values are represented as aggregate results rather than failures.

## 4. Classification

Classification combines column metadata, profiling evidence, data-domain rules, cross-column matches and explicit overrides. Its output is heuristic and deterministic, not semantic AI. Every discovered column has a registry record. Unresolved risk becomes `Dubbio`/`review_required`, not automatically `Non-PII`.

## 5. Protection policy

The registry selects one of twelve versioned rules. Nine consistency groups specify which columns must produce the same pseudonym for the same normalized source value. Core distinctions:

- **Masking:** replaces or redacts a value for a particular use context.
- **Pseudonymization:** replaces identifiers while intentionally retaining controlled linkability; HMAC rules in this project fall here.
- **Tokenization:** normally uses a separately managed token vault or mapping; this project does not implement a persistent token vault.
- **Anonymization:** aims to make re-identification no longer reasonably likely; this project does not claim anonymization.

## 6. Transactional masked load

The pipeline validates registry completeness and ambiguous-column decisions, computes deterministic mappings in memory, rebuilds the three masked schemas, loads tables in dependency order, recreates constraints and validates the result before commit. Failures roll back the transaction. The source schemas are never the write target.

## 7. Validation and evidence

Validation compares source/masked row counts, primary and foreign keys, unique constraints, declared and logical relationships, cross-table consistency groups, known PII patterns, source invariants and canonical checksums. The manifest contains aggregate counts, rule-use counts, collision statistics and checksums, not source values or mappings.

The verified 2026-10-08 run reported 20 processed tables, 2,063 source rows, 2,063 masked rows, 109 classified columns, 14 pipeline validations, zero schema-drift findings and successful idempotence.
