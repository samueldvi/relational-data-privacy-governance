# Security policy

## Versioni supportate

Riceve correzioni di sicurezza solo l'ultima versione presente su `main`. Tag e
branch storici sono baseline immutabili e non ricevono backport garantiti.

## Segnalazione

Usare la funzione **Report a vulnerability** nella scheda Security del
repository GitHub. Se la segnalazione privata non è disponibile, aprire una
issue priva di dettagli sfruttabili chiedendo un canale privato. Non pubblicare
proof-of-concept, credenziali, secret, dump, record personali o dati reali.

Indicare versione o commit, componente interessato, impatto, prerequisiti e una
riproduzione minima basata solo su dati sintetici. Non esiste una promessa di
SLA; le segnalazioni vengono valutate in base a impatto e disponibilità del
maintainer.

## Scope e limiti

Sono in scope pipeline Python, configurazioni di governance, container e
workflow versionati. Il PostgreSQL locale, Docker Desktop, runner GitHub e
piattaforme Informatica non sono gestiti da questo repository. L'implementazione
corrente è un proof of concept tecnico e non è autorizzata a trattare dati reali
senza una valutazione di sicurezza, privacy e governance specifica
dell'organizzazione adottante.

I report distinguono Critical, High e Medium. Un finding senza fix disponibile
viene conservato come artifact e valutato come rischio accettato o falso
positivo solo con motivazione versionata; non viene ignorato silenziosamente.
Critical e High correggibili bloccano il container scan.
