# Changelog

## [1.0.0] - 2026-08-05

### Added

- pipeline PostgreSQL per generazione sintetica, inventory, profiling,
  classificazione PII, masking e validazione;
- Privacy Metadata Registry per 109 colonne, 12 masking rule e 9 consistency
  group;
- CLI con otto comandi pubblici e manifest deterministico;
- documentazione di governance, architettura e trasferimento concettuale verso
  Informatica Data Privacy Management.

### Changed

- struttura applicativa consolidata come modular monolith con presentation,
  application, domain, ports e infrastructure layer;
- caricamento masked consolidato in una transazione con validazioni e rollback.

### Security

- HMAC-SHA-256 namespaced con secret esterno;
- mapping originale-pseudonimo mantenuti solo in memoria;
- profiling e testi liberi redatti prima della serializzazione;
- repository safety scanner e controlli CI su file sensibili.

### Validation

- 20 tabelle e 2.063 righe verificate sia negli schemi sorgente sia nei target
  masked;
- 159 test automatici, inclusi contract architetturali, rollback, idempotenza,
  determinismo e rilevamento PII;
- clean-environment validation e safety scanner completati con esito positivo.

### Known limitations

- discovery regex senza NER e rischio residuo sui pattern non riconosciuti;
- prestazioni non validate a scala enterprise;
- equivalenze funzionali Informatica da verificare su piattaforma autorizzata;
- validità di codici fiscali e IBAN sintetici limitata ai controlli formali.
