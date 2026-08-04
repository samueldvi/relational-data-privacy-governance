# Work Log

## 2026-08-04

| Inizio | Fine | Durata | Attività | Risultato |
|---|---|---:|---|---|
| 16:00 |  |  | Analisi della traccia e avvio del progetto | Traccia analizzata, chiarimento inviato a Nicola e repository locale inizializzato |

## Regole

- Registrare solo il tempo realmente lavorato.
- Aggiornare il log al termine di ogni blocco.
- Documentare problemi, decisioni e verifiche.
- Non ricostruire le ore a memoria a fine progetto.

| 16:00 | 17:03 | 1h 03m | Setup repository e PostgreSQL locale | Struttura creata, segreti separati, Docker Compose configurato su porta 5433, database healthy e pgcrypto verificato |
| 17:30 | 17:33 | 3m | Milestone 1: schema relazionale sintetico | Creato branch dedicato; consolidata D-003; aggiunte 6 tabelle HR, 6 Billing e 3 schemi masked; documentate le colonne trappola; validati 20/20 source table, constraint, relazioni logiche e idempotenza SQL |
| 17:41 | 17:48 | 7m | Milestone 2: generazione dati sintetici | Implementato caricamento transazionale deterministico di 2.063 righe su 20 tabelle; checksum CF/IBAN, PII testuale e colonne trappola validati; 13 test superati; corretti path pytest e conteggio atteso delle 12 FK dichiarate |
| 17:56 | 18:01 | 5m | Milestone 3: inventario tecnico | Inventariate 109 colonne su 20 tabelle e 3 schemi; rilevati 20 PK, 12 FK, 10 UNIQUE e 15 CHECK; confermate 2 relazioni logiche senza creare FK; corretta la gestione dell'unicità composta; 24 test superati |
| 18:04 | 18:21 | 17m | Milestone 4: profiling colonne | Profilate 109 colonne in snapshot read-only; rilevate 71 colonne con evidenze tecniche e 30 con pattern privacy; 220 campioni redatti; match al 100% per `cod_rif` e `rif_esterno`; falso positivo template segnalato; output byte-identico e 35 test superati |
