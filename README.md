# Relational Data Privacy Governance

[![CI](https://github.com/samueldvi/relational-data-privacy-governance/actions/workflows/ci.yml/badge.svg)](https://github.com/samueldvi/relational-data-privacy-governance/actions/workflows/ci.yml)

## TL;DR

Pipeline locale Python 3.12 e PostgreSQL 16 per generare dati sintetici, inventariare e classificare PII e creare copie masked relazionalmente coerenti.
Il risultato comprende 20 tabelle sorgente e 20 masked, governate da un registry completo di 109 colonne.
HMAC-SHA-256 namespaced, caricamento transazionale, rollback, idempotenza e checksum deterministici rendono il processo verificabile.
Il repository prepara concetti e controlli trasferibili verso Informatica Data Privacy Management, senza dichiarare un'integrazione diretta con la piattaforma.

## Risultati verificabili

| Evidenza | Risultato |
|---|---:|
| Schemi sorgente | 3 (`crm`, `hr`, `billing`) |
| Tabelle sorgente / masked | 20 / 20 |
| Colonne inventariate e classificate | 109 |
| Righe sintetiche sorgente / masked | 2.063 / 2.063 |
| Regole di masking | 12 |
| Consistency group | 9 |
| Test automatici | 159 superati nella suite finale |
| Manifest | checksum per tabella e globale, deterministici |

La suite verifica inoltre rollback completo, idempotenza con lo stesso secret,
output differenti con secret differenti, invarianti delle sorgenti, constraint,
relazioni dichiarate e logiche e assenza di PII rilevabile dalle regole note.

## Architettura

```mermaid
flowchart LR
    CLI["CLI"] --> APP["Application services"]
    APP --> DOMAIN["Pure domain"]
    APP --> PORTS["Repository ports"]
    INFRA["Infrastructure adapters"] --> PORTS
    INFRA --> DOMAIN
    INFRA --> PG[("PostgreSQL 16")]
    INFRA --> FILES["YAML / CSV / JSON"]
```

La fase Synthetic Data alimenta il Privacy Metadata Registry e le successive
validazioni tramite il flusso applicativo. La CLI chiama servizi applicativi iniettati dal composition root. L'application
layer definisce l'ordine end-to-end una sola volta; il dominio contiene regole
pure e l'infrastruttura incapsula PostgreSQL, configurazione e serializzazione.
I dettagli e i vincoli verificati sono in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### Architecture decisions

- **Modular monolith:** un solo deploy mantiene semplice la transazione masked e
  non introduce coordinamento distribuito senza un reale bisogno di scaling.
- **Dependency inversion:** application usa porte; gli adapter concreti vengono
  collegati solo da `src/bootstrap.py`.
- **Pure domain:** normalizzazione, HMAC, collisioni, redaction e checksum non
  leggono database, file o variabili d'ambiente.
- **Test boundaries:** test unitari domain/application non richiedono PostgreSQL;
  integrazione, contract architetturali e sicurezza restano separati.

## Quick start

Prerequisiti: Docker con Compose, Python 3.12 e una shell POSIX. Dalla root:

```bash
cp .env.example .env
# Sostituire in .env i placeholder con valori locali non riutilizzati altrove.
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
docker compose up -d
python -m src.cli all
```

Il container inizializza gli script `sql/00_...`–`sql/05_...` solo alla prima
creazione del volume. Per una validazione controllata da ambiente pulito usare
lo script documentato in `scripts/validate_clean_environment.sh`; il reset non
è mai implicito.

## CLI

| Comando | Funzione |
|---|---|
| `python -m src.cli status` | Stato aggregato di database, registry, manifest e branch |
| `python -m src.cli generate --seed 20260804` | Generazione deterministica delle 2.063 righe sintetiche |
| `python -m src.cli inventory` | Inventario e relazioni in `output/*.csv` |
| `python -m src.cli profile` | Profiling aggregato e campioni redatti |
| `python -m src.cli classify` | Registry YAML, catalogo CSV e classificazione Markdown |
| `python -m src.cli mask --dry-run` | Precondizioni e piano senza scritture |
| `python -m src.cli mask` | Creazione e caricamento transazionale degli schemi masked |
| `python -m src.cli mask --validate-only` | Controllo read-only dello stato masked |
| `python -m src.cli validate` | Validazione integrata e confronto col manifest |
| `python -m src.cli validate --check-idempotence` | Due esecuzioni equivalenti e confronto deterministico |
| `python -m src.cli all` | Pipeline completa, interrotta al primo errore |

Ogni comando restituisce un exit code non nullo in caso di errore e stampa solo
conteggi, stati, durate, statistiche e checksum. Non stampa credenziali,
mapping, pseudonimi o record completi.

## Componenti e output

- `src/cli/`: parser e comandi di presentazione compatibili;
- `src/application/`: servizi e orchestrazione end-to-end;
- `src/domain/`: modelli e logica privacy deterministica pura;
- `src/ports/`: contratti per database, configurazione, secret, clock e artefatti;
- `src/infrastructure/`: adapter PostgreSQL, YAML/CSV/JSON, ambiente e tempo;
- `src/bootstrap.py`: composition root;
- `src/apply_masking.py`, `src/inventory.py`, `src/profile_columns.py` e
  `src/classify.py`: entry point compatibili durante la migrazione incrementale.

Gli artefatti rigenerabili sono salvati in `output/` e ignorati da Git. Il
manifest contiene metadati aggregati, statistiche di collisione, controlli e
checksum, mai valori o mapping.

## Sicurezza e governance

- Il dataset è interamente sintetico e usa domini e numerazioni riservati ai test.
- `.env` è escluso da Git; segreto di masking e password restano esterni al codice.
- Le pseudonimizzazioni usano HMAC-SHA-256 con namespace separati per dominio e soggetto.
- I mapping vivono solo in memoria durante il batch e non vengono persistiti.
- Campioni di profiling e testi liberi sono redatti prima della scrittura degli output.
- Gli schemi sorgente sono verificati prima e dopo il masking e restano immutati.
- `billing.pagamenti.riferimento_bancario` resta `Dubbio`: D-008 autorizza solo
  `redact_detected_patterns`, con rischio residuo esplicitamente accettato.

Il repository è un ambiente didattico e dimostrativo. Non deve elaborare dati
reali senza threat model, gestione professionale delle chiavi, controlli IAM,
valutazione legale, monitoraggio e revisione del data owner.

## Limiti

- La discovery è regex e contestuale; non include Named Entity Recognition.
- Codici fiscali e IBAN sono formalmente validi, non verificati anagraficamente o bancariamente.
- Le prestazioni sono validate sul volume locale di 2.063 righe, non su scala enterprise.
- Il riferimento bancario eterogeneo può contenere valori sensibili non riconosciuti dalle regex.
- Non è disponibile un processo di re-identificazione: il mapping non viene conservato.
- Funzioni, nomi, licenze e capacità di Informatica devono essere verificati su un ambiente autorizzato.

## Trasferimento verso Informatica

Il progetto implementa localmente inventory, profiling, data domain, policy,
consistent masking, target masked, validazioni e audit tecnico. Questi concetti
costituiscono una base di analisi, non la prova che il repository utilizzi
Informatica direttamente. Il mapping, le verifiche di piattaforma e il piano di
adozione sono descritti in
[`docs/TRASFERIMENTO_INFORMATICA.md`](docs/TRASFERIMENTO_INFORMATICA.md).

## Demo web

Non è inclusa una web app. La valutazione in
[`docs/WEB_DEMO_FEASIBILITY.md`](docs/WEB_DEMO_FEASIBILITY.md) raccomanda una
demo statica alimentata esclusivamente da JSON aggregati e revisionati, senza
connessione al database o esecuzione del masking.

## Struttura del repository

```text
.
├── .github/workflows/       # CI PostgreSQL end-to-end
├── config/                  # domini, registry, regole, gruppi e decisioni operative
├── docs/                    # classificazione, decision log e documentazione tecnica
├── scripts/                 # validazione pulita e controlli di sicurezza
├── sql/                     # inizializzazione PostgreSQL ordinata
├── src/                     # pipeline e CLI Python
├── tests/                   # test unitari, integrazione, CLI, CI e sicurezza
├── compose.yml
├── requirements.txt
└── README.md
```

## Verifica locale

```bash
python -m src.cli status
python -m src.cli all
ruff check .
ruff format --check .
mypy src
coverage run -m pytest -q
coverage report
coverage xml
pre-commit run --all-files
python scripts/check_repository_safety.py
git diff --check
```

La baseline misurata sul branch di hardening è `23,6%` per i soli 14 test
unitari e `87,7%` per la suite completa di 159 test con PostgreSQL. Il gate
versionato usa `fail_under = 87`: mantiene un margine minimo per gli
arrotondamenti, ma fallisce in caso di regressione sostanziale rispetto alla
baseline verificata. `coverage.xml` è generato per le integrazioni esterne e
non è versionato.

Le decisioni effettivamente approvate sono versionate in
[`docs/DECISION_LOG.md`](docs/DECISION_LOG.md); le regole sono descritte in
[`docs/REGOLE_MASCHERAMENTO.md`](docs/REGOLE_MASCHERAMENTO.md).

## Release

La baseline `v1.0.0` è descritta nelle
[`release notes`](docs/RELEASE_NOTES_v1.0.0.md) e nel
[`CHANGELOG.md`](CHANGELOG.md). I gate verificati e quelli ancora richiesti
prima della pubblicazione sono registrati nella
[`release checklist`](docs/RELEASE_CHECKLIST.md).
