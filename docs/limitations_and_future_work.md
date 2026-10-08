# Limitations and future work

## Confirmed limitations

- The project handles synthetic data only and does not establish GDPR compliance.
- Classification and free-text discovery are deterministic heuristics based on metadata, patterns, profiling and overrides; no NER or semantic model is present.
- HMAC output is pseudonymized, not anonymized. Controlled equality remains and the secret is security-critical.
- Key management is environment-based. There is no KMS/HSM integration, rotation workflow or split operational role.
- One local PostgreSQL role is used for the demonstration; production least privilege and row/schema access policies are absent.
- The tested volume is 2,063 rows. Cumulative benchmark workloads do not prove enterprise-scale throughput.
- The ambiguous bank-reference rule can redact only recognized structures; its residual risk is accepted and documented.
- Informatica Data Privacy Management is not integrated or tested.
- No persistent mapping or re-identification service exists.
- Docker initialization scripts run automatically only on a new volume.

## Prioritized future work

1. Add a reviewed data-owner workflow and approval evidence before any real-data use.
2. Introduce managed secrets, rotation, least-privilege source/target roles and auditable operational identity.
3. Evaluate free-text NER and false-negative measurement on an authorized, representative corpus.
4. Add property-based tests for format-preserving primitives and larger-scale collision experiments.
5. Run controlled performance tests at realistic table sizes and document hardware, dataset shape and query timings.
6. Complete the migration from compatibility facades to repository-port implementations only if it simplifies maintenance without changing behavior.
7. Validate platform-specific rule mappings in an authorized Informatica environment before describing an integration.

A web dashboard, microservices split, and persistent token vault are not current proof-of-concept requirements. They should be added only for a concrete customer requirement, threat model, and validation plan. Authentication, authorization, managed secrets, operational monitoring, licensing, supported deployment, support ownership, and representative-data validation take priority for pilot readiness; see [commercial readiness](commercial_readiness.md).
