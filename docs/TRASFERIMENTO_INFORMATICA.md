# Trasferimento concettuale verso Informatica Data Privacy Management

## Scopo e perimetro

Questo documento descrive come i controlli realizzati nel repository possano
preparare un'adozione in un ambiente Informatica Data Privacy Management. Il
mapping è intenzionalmente concettuale: il repository non si collega alla
piattaforma e non dimostra disponibilità, denominazioni o licenze di funzioni
specifiche. Ogni equivalente enterprise deve essere verificato nell'ambiente e
nella versione effettivamente concessi al cliente.

## Implementato localmente

- inventory PostgreSQL di tabelle, colonne, constraint e relazioni;
- profiling aggregato, normalizzazione e discovery regex/contestuale;
- classificazione di tutte le colonne e data domain versionati;
- masking rule collegate al Privacy Metadata Registry;
- consistent masking cross-tabella mediante consistency group;
- HMAC-SHA-256 con secret esterno e namespace per dominio e soggetto;
- elaborazione batch ordinata e collision handling deterministico;
- schemi target masked separati, creati e popolati in transazione;
- manifest deterministico con checksum per tabella e globale;
- validazione di struttura, cardinalità, relazioni, cleartext rilevabile,
  idempotenza, rollback e invarianti delle sorgenti;
- audit tecnico tramite Decision Log, Work Log, configurazioni e output aggregati.

## Trasferibile concettualmente

Sono candidati al trasferimento la tassonomia dei domini, le policy di masking,
i gruppi di coerenza, le regole di discovery, l'associazione fra sorgenti e
target, la separazione degli ambienti, l'orchestrazione, l'audit e la
separazione dei permessi. Il trasferimento richiede una nuova validazione:
l'implementazione locale dimostra requisiti e casi di test, non configura
automaticamente la piattaforma enterprise.

## Da verificare sulla piattaforma

Con accesso autorizzato occorre verificare:

- nomi esatti e disponibilità delle funzionalità nella versione acquistata;
- flusso di configurazione nell'interfaccia e possibilità di promozione fra ambienti;
- connettività e supporto specifico per versione e modalità PostgreSQL;
- custodia, rotazione, segregazione e audit delle chiavi;
- comportamento e prestazioni del masking sul volume atteso;
- eventuale reversibilità controllata e relativo modello autorizzativo;
- integrazione IAM, ruoli applicativi e separazione dei compiti;
- lineage tecnico, reporting, scheduling e API disponibili;
- limiti di licenza, concorrenza, retention dei log e supporto operativo.

Non devono essere introdotti nei documenti nomi di schermate, menu o componenti
prima di una verifica diretta sulla piattaforma del cliente.

## Tabella di mapping

| Concetto locale | Implementazione nel repository | Equivalente concettuale enterprise | Verifica richiesta | Rischio o nota |
|---|---|---|---|---|
| Inventory | `src/inventory.py`, `output/inventory.csv` | Catalogo tecnico delle sorgenti | Connettore e metadati PostgreSQL supportati | Differenze nei tipi o constraint esposti |
| Profiling | `src/profile_columns.py` | Analisi statistica e discovery | Pattern, campionamento, soglie e costi | Regex locali non equivalgono a discovery enterprise |
| Data domain | `config/data_domains.yml` | Tassonomia dei dati sensibili | Modello di dominio e versionamento disponibili | Semantiche o granularità differenti |
| Registry | `config/pii_registry.yml` | Catalogo di classificazione governato | Ownership, workflow di review e import | Il registry locale resta la baseline, non la fonte runtime enterprise |
| Masking rule | `config/masking_rules.yml` | Policy o trasformazione di protezione | Primitive, formati e parametrizzazione | Output non necessariamente byte-identico |
| Consistency group | `config/consistency_groups.yml` | Coerenza fra colonne e sistemi | Scope, normalizzazioni e chiavi di correlazione | Cross-environment correlation da evitare |
| HMAC e namespace | `src/masking.py` | Derivazione deterministica protetta | Algoritmi, key management e rotazione | Una rotazione cambia tutti gli pseudonimi |
| Batch e collisioni | `resolve_collisions` | Gestione deterministica dell'unicità | Garanzie UNIQUE e comportamento a volume | Collisioni rare ma operative, non solo probabilistiche |
| Target masked | `masked_crm`, `masked_hr`, `masked_billing` | Ambiente target non-production | DDL, sequence, constraint e permessi | Le relazioni logiche non vanno promosse a FK |
| Manifest | `output/masking_manifest.json` | Evidenza di esecuzione e riconciliazione | Export, firma, retention e audit | Il manifest non deve contenere mapping o campioni |
| Validazione | `src/apply_masking.py`, `src.cli validate` | Controlli post-job e gate di rilascio | Exit status, metriche, alert e approvazioni | La discovery mantiene falsi negativi residui |
| Audit tecnico | log, configurazioni e decisioni versionate | Audit trail e reporting operativo | Immutabilità, retention e accesso | Git non sostituisce un sistema GRC o SIEM |

## Piano di adozione

1. Ottenere accesso controllato e inventariare versione, licenze, ambienti e ruoli.
2. Validare connettività, metadati e caratteristiche delle sorgenti PostgreSQL.
3. Sottoporre registry, colonne `Dubbio` e responsabilità alla review dei data owner.
4. Configurare e versionare i domini approvati in un ambiente non-production.
5. Definire regole, namespace, gestione delle chiavi e criteri di collisione.
6. Eseguire una prova su un subset sintetico o formalmente autorizzato.
7. Riconciliare PK, FK, UNIQUE, join e relazioni logiche sul target.
8. Misurare throughput, finestre, concorrenza, restart e rollback a volume rappresentativo.
9. Validare audit, alert, reporting, retention e segregazione dei permessi.
10. Procedere con rollout controllato, criteri di rollback e approvazione formale.

## Domande da porre al cliente

- Chi è data owner per ciascun dominio e chi approva le colonne dubbie?
- Quali casi richiedono pseudonimizzazione reversibile e con quale autorizzazione?
- Quali retention si applicano a sorgenti, target, log, report e chiavi?
- Quali ambienti esistono e quali trasferimenti fra ambienti sono consentiti?
- Chi può configurare, eseguire, approvare e leggere gli output?
- Quali SLA, volumi, picchi e finestre di esecuzione devono essere rispettati?
- Sono richiesti restart, rollback, incrementalità o near-real-time?
- Quali report, evidenze e integrazioni di monitoring sono obbligatori?
- Quali framework normativi, basi giuridiche e policy interne si applicano?
- Chi accetta formalmente il rischio residuo di discovery e redaction?
- Quali API e sistemi IAM, ticketing, lineage o SIEM devono essere integrati?
- Come vengono gestite rotazione, escrow, revoca e distruzione delle chiavi?

## Criterio di uscita

Il trasferimento può considerarsi validato solo quando equivalenze funzionali,
prestazioni, sicurezza, ruoli, audit e limiti di licenza sono dimostrati sulla
piattaforma autorizzata e approvati dai responsabili. La sola corrispondenza
terminologica non è sufficiente.
