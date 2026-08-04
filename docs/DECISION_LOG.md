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

**Stato:** in attesa di chiarimento

**Decisione provvisoria:** non implementare ancora lo schema di destinazione.

**Motivazione:** è stato chiesto a Nicola se utilizzare uno schema unico oppure tre schemi distinti.

---

## D-003 — Struttura dell'output masked

**Stato:** approvata

**Decisione:** creare tre schemi distinti:
- `masked_crm`
- `masked_hr`
- `masked_billing`

**Motivazione:** la separazione originale deve essere preservata perché in produzione i permessi sono diversi per schema e il masking non deve modificarli.

**Fonte:** chiarimento di Nicola del 2026-08-04.
