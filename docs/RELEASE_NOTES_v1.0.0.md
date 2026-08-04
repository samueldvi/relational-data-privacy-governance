# Relational Data Privacy Governance v1.0.0

## Overview

Questa release prepara una pipeline PostgreSQL riproducibile per inventario
tecnico, profiling, classificazione PII, pseudonimizzazione deterministica,
consistent masking, validazione e produzione di un manifest verificabile. Il
dataset incluso nel progetto è esclusivamente sintetico.

## Highlights

- architettura modular monolith con CLI, application services, dominio puro,
  porte e adapter infrastrutturali;
- 20 tabelle sorgente e 20 tabelle masked;
- 2.063 righe sorgente e 2.063 righe masked;
- Privacy Metadata Registry completo di 109 colonne;
- 12 masking rule e 9 consistency group;
- pseudonimizzazione HMAC-SHA-256 con namespace e collision handling
  deterministico;
- caricamento PostgreSQL transazionale con rollback e validazioni post-load;
- idempotenza e coerenza cross-tabella;
- CLI end-to-end e workflow CI con PostgreSQL 16;
- test architetturali e safety scanner del repository;
- documentazione per il trasferimento concettuale verso Informatica Data
  Privacy Management, senza dichiarare un'integrazione operativa.

## Verified results

Verifica locale eseguita il 2026-08-05 sul commit `main` `0797ce9`:

| Evidenza | Risultato |
|---|---:|
| Test automatici | 159 superati |
| Tabelle sorgente / masked | 20 / 20 |
| Righe sorgente / masked | 2.063 / 2.063 |
| Colonne classificate | 109 |
| Masking rule | 12 |
| Consistency group | 9 |
| Validazioni manifest | 14 |
| Safety scanner | 121 file, 0 violazioni |
| Clean-environment validation | superata |
| Checksum manifest | `84cfad4d80458b77ff2c63813885b9a3843db25db7e139e01d973a4c35451e78` |
| Job CI richiesto | `tests` configurato; esito remoto da confermare |

Il checksum include il commit Git nei metadati del manifest. Un nuovo commit
documentale può quindi cambiare il checksum globale senza modificare le
checksum delle tabelle masked.

## Public CLI

```bash
python -m src.cli generate
python -m src.cli inventory
python -m src.cli profile
python -m src.cli classify
python -m src.cli mask
python -m src.cli validate
python -m src.cli all
python -m src.cli status
```

## Security

- i dati elaborati dal progetto sono esclusivamente sintetici;
- secret di masking e credenziali PostgreSQL sono forniti dall'ambiente e non
  versionati;
- nessun mapping originale-pseudonimo viene persistito;
- gli schemi sorgente restano immutati durante il masking;
- campioni e testi liberi sono redatti prima della serializzazione;
- il progetto non è destinato a dati reali senza threat model, key management,
  IAM, monitoraggio, valutazione legale e approvazione del data owner.

## Known limitations

- la discovery usa regex e contesto, senza Named Entity Recognition;
- prestazioni e concorrenza non sono validate a scala enterprise;
- `billing.pagamenti.riferimento_bancario` conserva il rischio residuo di valori
  sensibili non riconosciuti dalle regex approvate;
- funzionalità, licenze e semantiche Informatica devono essere verificate sulla
  piattaforma effettivamente autorizzata;
- codici fiscali e IBAN sintetici hanno validità formale, non anagrafica o
  bancaria.

## Documentation

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Classificazione PII](CLASSIFICAZIONE_PII.md)
- [Regole di mascheramento](REGOLE_MASCHERAMENTO.md)
- [Trasferimento verso Informatica](TRASFERIMENTO_INFORMATICA.md)
- [Fattibilità demo web](WEB_DEMO_FEASIBILITY.md)
- [Branch protection](BRANCH_PROTECTION.md)
- [Release checklist](RELEASE_CHECKLIST.md)
