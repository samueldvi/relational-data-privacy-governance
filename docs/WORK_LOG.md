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
