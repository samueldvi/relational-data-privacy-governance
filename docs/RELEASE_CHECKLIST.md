# Release checklist — `v1.0.0`

Data della verifica locale: **2026-08-05**

Commit `main` verificato: **`0797ce9`**

Una voce è marcata solo quando è stata osservata direttamente. Le verifiche
GitHub non accessibili dalla sessione corrente restano intenzionalmente aperte.

## Repository e governance

- [x] `main` aggiornato e allineato a `origin/main`.
- [ ] Ultimo workflow CI su `main` concluso con job richiesto `tests` verde.
- [ ] Branch protection effettivamente attiva su `main` secondo
  `docs/BRANCH_PROTECTION.md`.
- [x] Working tree pulito al termine della validazione di `main`.
- [x] Tag locale e remoto `v1.0.0` non esistente prima della preparazione.

## Validazione tecnica

- [x] Pipeline end-to-end verde: 20 tabelle sorgente, 20 masked e 2.063 righe
  per ciascun lato.
- [x] Registry completo: 109 colonne, 12 masking rule e 9 consistency group.
- [x] Manifest con 14 validazioni e stato `success`.
- [x] Suite completa verde: 159 test.
- [x] Test architetturali verdi.
- [x] Idempotenza, determinismo e rollback verificati dalla pipeline e dalla
  suite automatica.
- [x] Clean-environment validation verde.
- [x] Safety scanner verde: 121 file tracciati ispezionati, 0 violazioni.
- [x] Checksum registrato:
  `84cfad4d80458b77ff2c63813885b9a3843db25db7e139e01d973a4c35451e78`.

## Documentazione e sicurezza

- [x] README completo e coerente con 159 test e l'architettura modular monolith.
- [x] Documentazione tecnica, privacy, Informatica, demo e branch protection
  presente.
- [x] Nessun secret, DSN completo, password reale, dump, mapping
  originale-pseudonimo o output sensibile versionato.
- [x] `.env` ignorato da Git.
- [x] Nessun percorso locale, email personale non necessaria o file temporaneo
  tracciato.
- [x] Nessun `TODO` o `FIXME` bloccante rilevato.
- [x] Release notes `v1.0.0` pronte.
- [x] Changelog aggiornato con la sola baseline realmente presente.

## Gate di pubblicazione

La release non è pubblicabile finché le due verifiche GitHub aperte non sono
confermate, la PR di preparazione non è integrata e `main` non viene nuovamente
validato. Dopo tali conferme, creare il tag annotato dal nuovo `main`, pubblicare
la GitHub Release usando `docs/RELEASE_NOTES_v1.0.0.md` e completare il controllo
post-release.
