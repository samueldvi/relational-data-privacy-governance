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
