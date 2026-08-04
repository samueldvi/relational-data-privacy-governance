# Protezione consigliata per `main`

## Scopo

Questa configurazione protegge il branch di rilascio del repository senza
modificare le impostazioni GitHub automaticamente. Deve essere applicata da un
amministratore del repository tramite una ruleset o una branch protection rule
con target esatto `main`.

## Regole richieste

| Impostazione GitHub | Valore consigliato | Motivazione nel progetto |
|---|---|---|
| Require a pull request before merging | Attiva | Evita commit applicativi, documentali o di configurazione eseguiti direttamente su `main`. |
| Required status checks | `tests` | Corrisponde all'unico job del workflow `.github/workflows/ci.yml`. Include pipeline PostgreSQL, contract architetturali, suite completa e safety scanner. |
| Require branches to be up to date before merging | Attiva | Verifica la combinazione effettiva tra PR e ultimo `main` prima del merge. |
| Require conversation resolution before merging | Attiva | Impedisce il merge con osservazioni tecniche o di governance ancora aperte. |
| Block force pushes | Attiva | Preserva la cronologia delle decisioni, delle validazioni e dei rilasci. |
| Block branch deletion | Attiva | Impedisce la rimozione accidentale del branch di default. |
| Allow deletions | Disattiva | Equivale al blocco della cancellazione di `main`. |
| Allow force pushes | Disattiva | Nessun attore deve riscrivere la storia di `main`. |

## Review

Se il repository ha almeno due collaboratori effettivi, configurare anche:

- almeno **una approving review**;
- dismiss stale approvals quando nuovi commit modificano la PR;
- richiedere una nuova approvazione dopo modifiche successive all'ultima review;
- includere gli amministratori nelle regole, salvo una procedura di emergenza
  documentata e sottoposta ad audit.

Per un repository personale senza un secondo reviewer reale, non simulare
l'approvazione: mantenere tutti gli altri gate e attivare la review obbligatoria
quando viene aggiunto un collaboratore responsabile.

## Configurazione operativa

1. Aprire **Settings → Rules → Rulesets** e creare una ruleset per il branch di
   default, oppure usare **Branches → Branch protection rules**.
2. Impostare il pattern di destinazione esattamente a `main`.
3. Abilitare le regole indicate sopra.
4. Selezionare `tests` solo dopo che il workflow `CI` ha completato almeno una
   volta sul repository, così GitHub lo espone tra gli status check disponibili.
5. Non concedere bypass permanenti. Eventuali bypass di emergenza devono essere
   limitati nel tempo e registrati con motivazione e revisione successiva.

## Verifica dopo l'attivazione

Usare una PR documentale non critica per verificare che:

- il merge resti bloccato mentre `tests` è in esecuzione o fallisce;
- il merge resti bloccato con conversazioni irrisolte;
- un aggiornamento di `main` renda la PR non aggiornata;
- push diretto, force push e cancellazione di `main` siano rifiutati;
- la regola di review si applichi soltanto quando è disponibile un reviewer
  indipendente.

La configurazione GitHub effettiva resta un controllo amministrativo esterno al
repository e deve essere verificata separatamente prima di dichiarare pronta la
release `v1.0.0`.
