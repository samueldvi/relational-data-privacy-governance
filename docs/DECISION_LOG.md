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

---

## D-005 — Determinismo e sicurezza del dataset sintetico

**Stato:** approvata

**Decisione:** costruire l'intero dataset con un seed esplicito e una data di
riferimento fissa (`2025-12-31`), usando domini email `example.test`, numerazioni
telefoniche marcate come sintetiche e generatori locali per codici fiscali e
IBAN dotati di checksum formale. Il reset usa `TRUNCATE ... RESTART IDENTITY`
in un'unica transazione e non modifica la struttura del database.

**Motivazione:** una data corrente renderebbe l'output instabile; namespace
pubblici o dati hardcoded potrebbero invece coincidere con persone reali. La
costruzione completa prima del caricamento rende inoltre ripetibile l'ordine
delle operazioni e impedisce carichi parziali in caso di errore.

---

## D-006 — Registry privacy come fonte primaria e fallback conservativo

**Stato:** approvata

**Decisione:** usare `config/pii_registry.yml` come fonte strutturata primaria
per tutte le 109 colonne e generare da essa catalogo CSV e documentazione
Markdown. Le regole combinano inventario, profiling, contesto e override; un
caso non risolto con motivazione concreta deve diventare `Dubbio` con stato
`review_required`, mai `Non-PII` per semplice assenza di pattern.

**Motivazione:** la completezza della copertura prevale sull'automazione. Un
falso negativo lascerebbe PII esposta, mentre un dubbio esplicito conserva
evidenza, rischio e responsabilità della revisione umana.

---

## D-007 — Derivazione HMAC namespaced e collisioni deterministiche

**Stato:** approvata

**Decisione:** derivare ogni pseudonimo con HMAC-SHA-256 su namespace, valore
normalizzato e, solo in caso di collisione, contatore di retry. Elaborare gli
input distinti in ordine normalizzato, mantenere il mapping esclusivamente in
memoria e separare i namespace per dominio e soggetto. Gli IBAN sintetici usano
ABI e CAB `00000`, numero di conto derivato e checksum MOD-97 valido.

**Motivazione:** la separazione impedisce correlazioni involontarie tra domini
o soggetti, l'ordinamento rende il risultato indipendente dall'ordine delle
righe e il contatore risolve collisioni senza affidarsi alla sola probabilità.
ABI e CAB nulli mantengono il formato ma rendono l'output non instradabile.
