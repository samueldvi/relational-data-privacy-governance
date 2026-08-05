# Data-owner review process

Le colonne ambigue restano `Dubbio` finché una review versionata non autorizza
una strategia. Gli stati ammessi sono `open`, `under_review`, `approved`,
`rejected` ed `expired`. Solo `approved`, con approvatore, rischio residuo,
strategia e data futura, abilita l'uso operativo.

`python -m src.cli reviews` valida il registro e stampa esclusivamente conteggi
aggregati. Review mancanti, scadute, senza approvatore, senza rischio residuo o
con strategia diversa dalla decisione approvata causano exit code non nullo.
Il rinnovo richiede evidenza aggiornata e una nuova decisione versionata.
