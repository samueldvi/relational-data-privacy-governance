# Decision Log

## D-001 — Stack locale

**Stato:** approvata

**Decisione:** utilizzare PostgreSQL locale tramite Docker Compose, Python e pgcrypto.

**Motivazione:** è lo stack richiesto dalla traccia e consente un ambiente riproducibile.

---

## D-002 — Gestione del segreto di masking

**Stato:** approvata

**Decisione:** leggere il salt da una variabile d'ambiente e non inserirlo mai nel codice o nel repository.

**Motivazione:** il segreto deve rimanere esterno all'applicazione e non deve essere versionato.

---

## D-003 — Struttura dell'output masked

**Stato:** approvata

**Decisione:** creare tre schemi distinti:
- `masked_crm`
- `masked_hr`
- `masked_billing`

**Motivazione:** la separazione originale deve essere preservata perché in produzione i permessi sono diversi per schema e il masking non deve modificarli.

**Fonte:** chiarimento di Nicola del 2026-08-04.

---

## D-004 — Collocazione delle colonne PII con nome fuorviante

**Stato:** approvata

**Decisione:** aggiungere `cod_rif` a `billing.sconti` e `rif_esterno` a
`billing.pagamenti`. Durante la generazione, la prima conterrà codici fiscali
già presenti in `crm.clienti.cod_fisc`, la seconda email già presenti in
`crm.clienti.email`.

**Motivazione:** entrambi i nomi sono plausibili nel contesto delle rispettive
tabelle ma non rivelano la natura PII dei valori. Questo consente di verificare
che profiling, confronto dei valori e relazioni cross-tabella integrino la
classificazione basata sul nome. Non vengono aggiunte FK perché le dipendenze
sono logiche e devono restare tali.
