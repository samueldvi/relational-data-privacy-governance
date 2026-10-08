# Commercial readiness assessment and product roadmap

## Current maturity

Relational Data Privacy Governance is a validated B2B technical proof of concept. It demonstrates an end-to-end PostgreSQL privacy-governance workflow and is suitable for architecture review, engineering evaluation, and controlled experimentation on synthetic or explicitly approved non-production data.

It is not currently a production product, hosted SaaS service, supported enterprise distribution, or compliance-certified control.

## Readiness matrix

| Capability | Current state | Pilot requirement | Production requirement | Priority |
|---|---|---|---|---|
| Core data workflow | Implemented and regression-tested | Preserve evidence and define supported configurations | Versioned compatibility and migration policy | P0 |
| Authentication | Not implemented | Service/CLI identity; enterprise SSO decision | SSO/OIDC, workload identity, MFA policy where applicable | P0 |
| Authorization | Database credential boundary only | Separate source-reader and target-writer roles | RBAC/ABAC, policy administration, least privilege, tenant isolation | P0 |
| Secret management | Environment variables | Managed secret store and rotation procedure | KMS/HSM integration, key versioning, revocation, access audit | P0 |
| Operational audit | Local aggregate manifest | Structured immutable export with actor/run identity | Central retention, search, alerting, evidence lifecycle | P0 |
| Monitoring | CLI exit codes and CI | Metrics, health, alerting, run correlation | SLOs, tracing, capacity and anomaly monitoring | P0 |
| Deployment | Local Compose and CI container | Signed, pinned pilot artifacts and deployment guide | Supported orchestrator, HA, upgrades, rollback, DR | P0 |
| Real-world validation | Synthetic workload only | Authorized representative corpus and acceptance criteria | Continuous quality measurement across supported domains | P0 |
| Privacy/legal governance | Technical controls only | Data-acceptance policy and organization review | DPIA/legal process, records of processing, retention governance | P0 |
| Licensing/IP | Repository history and notices only | Select and publish product license; confirm ownership | Commercial terms, third-party obligations, export review | P0 |
| Support | No support commitment | Named pilot owner and escalation route | Support tiers, vulnerability SLA, lifecycle and EOL policy | P1 |
| Performance | Small reference workload | Pilot volume benchmark and resource limits | Capacity model, scale tests, concurrency and cost targets | P1 |
| Free-text detection | Regex and dictionary | Measure precision/recall on authorized samples | Governed NLP/NER options and human review workflow | P1 |
| Policy workflow | Version-controlled files | Reviewed change/approval process | UI/API, separation of duties, policy lifecycle and lineage | P1 |
| Integrations | PostgreSQL and local artifacts | Define customer-driven connector scope | Supported APIs/connectors with compatibility contracts | P2 |

## Entry criteria for a controlled pilot

A pilot should not start until all of the following are true:

1. the dataset is synthetic or formally approved non-production data;
2. source read and protected-target write privileges are separated;
3. authentication and accountable run identity exist;
4. the masking key is stored and rotated through an approved managed service;
5. execution events are exported to an access-controlled immutable audit destination;
6. network, storage, retention, backup, and cleanup boundaries are documented;
7. incident ownership and stop criteria are assigned;
8. representative-data classification and transformation acceptance criteria are agreed;
9. a product license and third-party dependency obligations are confirmed;
10. the organization accepts the documented residual risks.

## Prioritized roadmap

### P0 — Proof of concept to pilot

- publish a threat model, data-flow diagram, and trust-boundary review;
- define a supported configuration schema and release compatibility policy;
- implement workload identity and role-based authorization;
- create distinct metadata-reader, source-reader, and protected-writer database roles;
- integrate a managed secret provider with versioned keys and rotation;
- add structured audit events containing run identity, policy version, counts, checks, and status without data values;
- add health metrics, failure alerts, correlation IDs, retention, and cleanup controls;
- ship signed/pinned deployment artifacts and a pilot operations guide;
- conduct representative authorized-data validation and record false positives/negatives;
- select a repository/product license and document third-party obligations;
- define pilot ownership, support channel, vulnerability response, and acceptance gates.

### P1 — Pilot to production candidate

- support resumable and partitioned processing for larger tables;
- add backup/restore, disaster-recovery rehearsal, and deployment rollback;
- establish performance and capacity baselines for supported workload classes;
- add policy approval, separation of duties, and change evidence;
- implement retention and deletion controls for protected datasets and audit records;
- commission independent security testing and remediate findings;
- formalize data-protection impact and legal review with the adopting organization;
- define release cadence, semantic versioning, supported versions, and EOL policy.

### P2 — Enterprise product expansion

- add multi-tenant isolation only after the security model is independently validated;
- introduce governed APIs and connectors driven by validated customer demand;
- support incremental refresh, lineage catalogs, and event-driven workflows;
- evaluate optional NLP/NER-assisted discovery with measurable quality and review queues;
- build administration and approval interfaces where they reduce operational risk;
- establish commercial packaging, service levels, customer onboarding, and support operations.

## Risks that remain after the current hardening

- Deterministic pseudonyms preserve linkability by design.
- Free-text redaction can miss unknown formats and contextual identifiers.
- The reference dataset is too small and regular to establish enterprise performance or classification quality.
- A compromised HMAC secret permits recomputation of identifiers.
- Preserved technical keys can create linkage risk in other schemas or external systems.
- Local aggregate manifests are not equivalent to immutable enterprise audit logs.
- Configuration review through Git does not by itself establish separation of duties.
- Passing tests does not prove secure deployment, regulatory compliance, or operational resilience.

## Commercial positioning guardrails

Public material should describe the repository as a validated proof of concept or reference implementation. It should not claim customer deployments, regulatory certification, enterprise scale, commercial support, integration with named third-party platforms, or production readiness unless separately evidenced.

Verified figures must remain associated with the dated synthetic reference workload. Roadmap capabilities must always be labeled as proposed or planned rather than available.
