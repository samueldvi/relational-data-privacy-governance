# Valutazione di fattibilità della demo web

## Obiettivo e vincoli

Una futura demo dovrebbe rendere leggibili architettura, conteggi aggregati,
copertura delle classificazioni, categorie PII, masking rule, consistency
group, stato delle validazioni, checksum e confronto strutturale source/masked.
Gli eventuali esempi devono essere sintetici, ulteriormente redatti e separati
dal database locale.

La demo non deve mostrare o ricevere secret, password, DSN, mapping
originale-pseudonimo, record completi, testi liberi originali o valori letti dal
database. Non deve permettere di avviare il masking da Internet.

## Opzioni tecniche

| Opzione | Vantaggi | Costi e limiti | Profilo di sicurezza |
|---|---|---|---|
| Streamlit | Sviluppo rapido, integrazione Python, grafici e filtri semplici | Personalizzazione limitata, runtime da mantenere, gestione sessioni e deployment | Accettabile solo senza DB e con artefatti aggregati; superficie server comunque presente |
| FastAPI + frontend leggero | Separazione API/UI, controllo su contratti e caching, estendibilità | Maggiore complessità, due componenti da testare e distribuire, manutenzione e osservabilità | Buon controllo ma superficie più ampia; non giustificata per dati statici |
| Sito statico | Hosting economico, GitHub Pages, nessun backend o accesso DB, revisione degli artefatti prima del deploy | Nessuna esecuzione live del masking; interazioni limitate al browser | Opzione più sicura: JSON preaggregati, Content Security Policy e nessun secret runtime |

## Raccomandazione

Per un repository pubblico o dimostrativo si raccomanda un **sito statico**.
Una fase di build deve leggere esclusivamente un JSON aggregato, sottoposto a
schema validation e repository safety check, e produrre grafici e tabelle senza
accesso a PostgreSQL. GitHub Pages è adeguato se policy aziendali, visibilità e
approvazioni lo consentono.

Streamlit è una seconda scelta per workshop privati quando servono filtri più
rapidi, sempre con snapshot aggregato e senza credenziali. FastAPI più frontend
non offre un beneficio proporzionato finché non esistono requisiti autenticati
o aggiornamenti dinamici approvati.

## Dataset pubblico della demo

Il contratto JSON dovrebbe ammettere soltanto:

- conteggi di schemi, tabelle, colonne e righe;
- distribuzioni per categoria, regola e review status;
- nomi tecnici già pubblici nel repository, se approvati;
- elenco dei controlli e relativo esito booleano;
- checksum del manifest e versione Git;
- statistiche aggregate di collisione senza input o output pseudonimizzati.

Il processo di pubblicazione deve rifiutare campi inattesi e pattern compatibili
con email, CF, IBAN, telefoni, credenziali o DSN.

## Roadmap

1. Definire lo schema JSON aggregato e una whitelist di campi pubblicabili.
2. Progettare wireframe accessibili per architettura, copertura e validazioni.
3. Costruire un prototipo statico senza backend e con fixture revisionate.
4. Eseguire test di sicurezza, content scan, accessibilità e assenza di dati sensibili.
5. Configurare deployment, CSP, dipendenze bloccate e processo di approvazione.
6. Pubblicare il link nel README solo dopo review privacy e security.

## Criteri per rivalutare la scelta

Valutare Streamlit o un backend soltanto se emergono requisiti concreti di
sessione, simulazione parametrica o aggiornamento frequente non soddisfatti dal
browser. Anche in quel caso il servizio dovrebbe consumare dati aggregati e
mai connettersi al database del progetto.
