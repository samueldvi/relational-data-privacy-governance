# Relational Data Privacy Governance

Ambiente locale di studio per data discovery, classificazione PII e masking di
database relazionali. Tutti i record generati sono sintetici; il database deve
comunque essere trattato come materiale di test controllato perché simula PII.

## Generazione dei dati sintetici

Con PostgreSQL avviato sulla porta `5433`, dalla root del repository:

```bash
docker compose up -d
.venv/bin/python -m src.generate_data --seed 20260804
.venv/bin/pytest tests/test_generation.py -q
```

Il seed è obbligatoriamente esplicito nell'uso documentato. La stessa versione
del progetto, delle dipendenze e lo stesso seed producono lo stesso dataset; un
seed diverso produce dati diversi. Prima del caricamento il generatore svuota
in transazione le sole 20 tabelle sorgente con `TRUNCATE ... RESTART IDENTITY`:
non elimina né ricrea schemi o tabelle.

Email e telefoni usano namespace chiaramente sintetici. Codici fiscali e IBAN
non appartengono a persone reali: sono costruiti casualmente e includono un
checksum formalmente valido esclusivamente per i test.

## Inventario tecnico

Per rigenerare l'inventario delle colonne e l'analisi delle relazioni dalla
root del repository:

```bash
.venv/bin/python -m src.inventory
```

Il comando legge esclusivamente i metadati dei tre schemi sorgente e produce
`output/inventory.csv` e `output/logical_relationships.csv`. Gli output sono
deterministici, non contengono campioni di dati né credenziali e restano esclusi
da Git. Le relazioni suggerite non modificano i constraint del database.

## Profiling delle colonne

Per rigenerare le metriche aggregate e le evidenze tecniche di pattern:

```bash
.venv/bin/python -m src.profile_columns
```

Il risultato è `output/profiling_results.json`, ordinato e deterministico. I
campioni sospetti sono limitati a 20 per colonna e redatti prima della scrittura.
Il profiler confronta inoltre valori normalizzati tra colonne compatibili, ma
non assegna ancora alcuna classificazione PII definitiva.

Normalizzazioni usate nei confronti:

- email: trim e conversione lowercase;
- codice fiscale: trim e conversione uppercase;
- IBAN: rimozione degli spazi e conversione uppercase;
- telefono: conservazione dell'eventuale `+` iniziale e delle sole cifre;
- nomi: trim, lowercase e collasso degli spazi interni;
- testo libero: normalizzazione delle terminazioni di riga e trim, senza
  modificare il contenuto analizzato dai pattern.

## Privacy Metadata Registry e classificazione

Per combinare inventario, profiling, relazioni e override approvati:

```bash
.venv/bin/python -m src.classify
```

Il comando valida la copertura di tutte le colonne e genera:

- `config/pii_registry.yml`, fonte strutturata primaria e versionata;
- `output/pii_catalog.csv`, catalogo tabellare rigenerabile;
- `docs/CLASSIFICAZIONE_PII.md`, vista leggibile generata dal registry.

L'inventario descrive la struttura, il profiling raccoglie evidenze aggregate,
il registry applica regole contestuali e override, mentre la futura fase di
masking consumerà `masking_rule` e `consistency_group` senza riclassificare i
dati. I record `Dubbio` bloccano l'automazione fino alla revisione del data owner.
