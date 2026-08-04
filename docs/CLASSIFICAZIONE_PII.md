# Classificazione PII

> Documento generato deterministicamente da `config/pii_registry.yml`. Il registry strutturato è la fonte primaria.

## Sintesi generale

Colonne classificate: **109**. Nessuna colonna è esclusa dalla copertura.

| Categoria | Colonne |
| --- | --- |
| Dubbio | 1 |
| Non-PII | 17 |
| PII-diretta | 20 |
| PII-indiretta | 66 |
| PII-nascosta | 5 |

### Copertura per schema

| Schema | Colonne |
| --- | --- |
| billing | 35 |
| crm | 41 |
| hr | 33 |

### Stato della revisione

| Stato | Colonne |
| --- | --- |
| auto_proposed | 103 |
| confirmed | 4 |
| false_positive_confirmed | 1 |
| review_required | 1 |

## Colonne Dubbio

| Colonna | Dominio | Confidence | Motivazione | Revisione richiesta |
| --- | --- | --- | --- | --- |
| billing.pagamenti.riferimento_bancario | bank_reference | 0.45 | Il campo contiene riferimenti sintetici eterogenei e una quota di valori compatibili con codici fiscali; il data owner deve chiarire la semantica produttiva. | Validazione del data owner obbligatoria prima del masking. |

## Falsi positivi confermati

| Colonna | Dominio | Motivazione |
| --- | --- | --- |
| crm.campagne.email_template | business_metadata | Il contenuto usa segnaposto di template e non indirizzi personali effettivi; la forma simile a un'email non costituisce PII reale. |

## PII nascoste

| Colonna | Dominio | Soggetto | Regola prevista | Stato |
| --- | --- | --- | --- | --- |
| billing.pagamenti.rif_esterno | email_address | customer | mask_email | confirmed |
| billing.sconti.cod_rif | italian_tax_code | customer | mask_tax_code | confirmed |
| billing.solleciti.testo_sollecito | free_text_with_pii | customer | redact_free_text | auto_proposed |
| crm.note_cliente.testo | free_text_with_pii | customer | redact_free_text | auto_proposed |
| hr.valutazioni.commento | free_text_with_pii | employee | redact_free_text | auto_proposed |

## Relazioni rilevanti

| Colonna | Relazione dichiarata | Relazione logica |
| --- | --- | --- |
| billing.coordinate_bancarie.cliente_id | — | crm.clienti.cliente_id (logical_suspected) |
| billing.fatture.cliente_id | — | crm.clienti.cliente_id (logical_confirmed) |
| billing.pagamenti.fattura_id | billing.fatture.fattura_id | — |
| billing.sconti.cliente_id | — | crm.clienti.cliente_id (logical_suspected) |
| billing.solleciti.fattura_id | billing.fatture.fattura_id | — |
| crm.consensi.cliente_id | crm.clienti.cliente_id | — |
| crm.contatti_extra.cliente_id | crm.clienti.cliente_id | — |
| crm.indirizzi.cliente_id | crm.clienti.cliente_id | — |
| crm.note_cliente.cliente_id | crm.clienti.cliente_id | — |
| crm.ordini.cliente_id | crm.clienti.cliente_id | — |
| hr.buste_paga.dipendente_id | hr.dipendenti.dipendente_id | — |
| hr.dipendenti.reparto_id | hr.reparti.reparto_id | — |
| hr.presenze.dipendente_id | hr.dipendenti.dipendente_id | — |
| hr.reparti.responsabile_id | — | hr.dipendenti.dipendente_id (logical_confirmed) |
| hr.valutazioni.dipendente_id | hr.dipendenti.dipendente_id | — |
| hr.valutazioni.valutatore_id | hr.dipendenti.dipendente_id | — |

## Catalogo completo

| Schema | Tabella | Colonna | Categoria | Dominio | Soggetto | Confidence | Masking rule | Consistency group | Revisione | Motivazione |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| billing | coordinate_bancarie | coordinata_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | coordinate_bancarie | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | coordinate_bancarie | iban | PII-diretta | italian_iban | bank_account_holder | 0.99 | mask_iban | customer_iban | auto_proposed | Valori con struttura italiana e checksum IBAN valido, associati a conto o intestatario. |
| billing | coordinate_bancarie | intestatario | PII-diretta | person_name | bank_account_holder | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| billing | coordinate_bancarie | banca | Non-PII | business_metadata | not_applicable | 0.91 | preserve_value | — | auto_proposed | Denominazione sintetica dell'istituto, non dell'intestatario del conto. |
| billing | fatture | fattura_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | fatture | cliente_id | PII-indiretta | internal_identifier | customer | 1.00 | preserve_technical_key | — | confirmed | Identificativo che collega logicamente la fattura al cliente con match completo e nessun orfano, senza FK dichiarata. |
| billing | fatture | numero_fattura | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | fatture | data_emissione | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | fatture | importo | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | fatture | iva | Non-PII | financial_transaction | not_applicable | 0.90 | preserve_value | — | auto_proposed | Aliquota fiscale isolata, non identificante e comune a molte fatture. |
| billing | fatture | stato | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | pagamenti | pagamento_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | pagamenti | fattura_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | pagamenti | data_pagamento | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | pagamenti | importo_pagato | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | pagamenti | metodo | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | pagamenti | riferimento_bancario | Dubbio | bank_reference | customer | 0.45 | review_before_masking | — | review_required | Il campo contiene riferimenti sintetici eterogenei e una quota di valori compatibili con codici fiscali; il data owner deve chiarire la semantica produttiva. |
| billing | pagamenti | rif_esterno | PII-nascosta | email_address | customer | 1.00 | mask_email | customer_email | confirmed | I valori hanno sintassi email, sono normalizzati lowercase e coincidono con crm.clienti.email con match cross-tabella del 100%. |
| billing | report_mensili | report_id | Non-PII | internal_identifier | not_applicable | 0.94 | preserve_value | — | auto_proposed | Chiave tecnica della struttura operativa, priva di collegamento diretto a una persona nel modello corrente. |
| billing | report_mensili | mese | Non-PII | aggregate_metric | not_applicable | 0.99 | preserve_value | — | auto_proposed | Metrica mensile aggregata senza dettaglio individuale nel modello corrente. |
| billing | report_mensili | anno | Non-PII | aggregate_metric | not_applicable | 0.99 | preserve_value | — | auto_proposed | Metrica mensile aggregata senza dettaglio individuale nel modello corrente. |
| billing | report_mensili | totale_fatturato | Non-PII | aggregate_metric | not_applicable | 0.99 | preserve_value | — | auto_proposed | Metrica mensile aggregata senza dettaglio individuale nel modello corrente. |
| billing | report_mensili | totale_incassato | Non-PII | aggregate_metric | not_applicable | 0.99 | preserve_value | — | auto_proposed | Metrica mensile aggregata senza dettaglio individuale nel modello corrente. |
| billing | sconti | sconto_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | sconti | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | sconti | codice_sconto | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | sconti | percentuale | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | sconti | data_scadenza | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | sconti | cod_rif | PII-nascosta | italian_tax_code | customer | 1.00 | mask_tax_code | customer_tax_code | confirmed | Il nome è fuorviante, ma tutti i valori rispettano il formato fiscale e coincidono con crm.clienti.cod_fisc con match cross-tabella del 100%. |
| billing | solleciti | sollecito_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | solleciti | fattura_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| billing | solleciti | data_invio | PII-indiretta | financial_transaction | customer | 0.88 | preserve_value | — | auto_proposed | Attributo di una transazione o comunicazione collegata, direttamente o logicamente, a un cliente. |
| billing | solleciti | destinatario_email | PII-diretta | email_address | customer | 0.98 | mask_email | customer_email | auto_proposed | Sintassi email rilevata sui valori e normalizzazione case-insensitive disponibile per i confronti. |
| billing | solleciti | testo_sollecito | PII-nascosta | free_text_with_pii | customer | 0.99 | redact_free_text | — | auto_proposed | Il testo libero contiene pattern PII e nomi noti; richiede futura redaction multipattern e revisione dei limiti regex. |
| crm | campagne | campagna_id | Non-PII | internal_identifier | not_applicable | 0.94 | preserve_value | — | auto_proposed | Chiave tecnica della struttura operativa, priva di collegamento diretto a una persona nel modello corrente. |
| crm | campagne | nome_campagna | Non-PII | business_metadata | not_applicable | 0.94 | preserve_value | — | auto_proposed | Metadato di campagna sintetica non riferito a un interessato individuale. |
| crm | campagne | email_template | Non-PII | business_metadata | not_applicable | 1.00 | preserve_value | — | false_positive_confirmed | Il contenuto usa segnaposto di template e non indirizzi personali effettivi; la forma simile a un'email non costituisce PII reale. |
| crm | campagne | data_inizio | Non-PII | business_metadata | not_applicable | 0.94 | preserve_value | — | auto_proposed | Metadato di campagna sintetica non riferito a un interessato individuale. |
| crm | clienti | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | clienti | nome | PII-diretta | person_name | customer | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| crm | clienti | cognome | PII-diretta | person_name | customer | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| crm | clienti | email | PII-diretta | email_address | customer | 0.98 | mask_email | customer_email | auto_proposed | Sintassi email rilevata sui valori e normalizzazione case-insensitive disponibile per i confronti. |
| crm | clienti | telefono | PII-diretta | phone_number | customer | 0.98 | mask_phone | customer_phone | auto_proposed | Struttura telefonica coerente rilevata nei valori, non soltanto nel nome della colonna. |
| crm | clienti | cod_fisc | PII-diretta | italian_tax_code | customer | 0.99 | mask_tax_code | customer_tax_code | auto_proposed | Struttura di 16 caratteri e carattere di controllo validi, confermati dal profiling dei valori. |
| crm | clienti | data_nascita | PII-indiretta | birth_date | customer | 0.99 | shift_birth_date | — | auto_proposed | Data di nascita plausibile e contestualmente riferita al cliente, utilizzabile come quasi-identificatore. |
| crm | clienti | segmento | PII-indiretta | business_metadata | customer | 0.82 | preserve_value | — | auto_proposed | Attributo del profilo cliente che può contribuire alla segmentazione o correlazione quando unito all'identificativo. |
| crm | clienti | data_registrazione | PII-indiretta | technical_timestamp | customer | 0.82 | preserve_value | — | auto_proposed | Attributo del profilo cliente che può contribuire alla segmentazione o correlazione quando unito all'identificativo. |
| crm | consensi | consenso_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | consensi | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | consensi | tipo_consenso | PII-indiretta | consent_information | customer | 0.94 | preserve_value | — | auto_proposed | Informazione di consenso associata tramite chiave a un cliente e quindi parte del suo profilo privacy. |
| crm | consensi | data_consenso | PII-indiretta | consent_information | customer | 0.94 | preserve_value | — | auto_proposed | Informazione di consenso associata tramite chiave a un cliente e quindi parte del suo profilo privacy. |
| crm | consensi | revocato | PII-indiretta | consent_information | customer | 0.94 | preserve_value | — | auto_proposed | Informazione di consenso associata tramite chiave a un cliente e quindi parte del suo profilo privacy. |
| crm | contatti_extra | contatto_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | contatti_extra | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | contatti_extra | tipo | Non-PII | business_metadata | customer | 0.90 | preserve_value | — | auto_proposed | Discriminante del tipo di contatto; non contiene da solo il valore personale. |
| crm | contatti_extra | valore | PII-diretta | contact_value | customer | 0.98 | mask_contact_value | — | auto_proposed | Il discriminante di riga e il profiling mostrano valori email o telefono direttamente utilizzabili per contattare il cliente. |
| crm | indirizzi | indirizzo_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | indirizzi | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | indirizzi | via | PII-diretta | postal_address | customer | 0.95 | mask_postal_address | — | auto_proposed | Componente granulare dell'indirizzo postale collegata tramite foreign key a un cliente. |
| crm | indirizzi | cap | PII-indiretta | geographic_information | customer | 0.90 | preserve_value | — | auto_proposed | CAP formalmente coerente e collegato all'indirizzo del cliente; costituisce un quasi-identificatore geografico. |
| crm | indirizzi | citta | PII-indiretta | geographic_information | customer | 0.88 | preserve_value | — | auto_proposed | Componente geografica collegata a un cliente, utile alla re-identificazione in combinazione con altri attributi. |
| crm | indirizzi | provincia | PII-indiretta | geographic_information | customer | 0.88 | preserve_value | — | auto_proposed | Componente geografica collegata a un cliente, utile alla re-identificazione in combinazione con altri attributi. |
| crm | note_cliente | nota_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | note_cliente | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | note_cliente | testo | PII-nascosta | free_text_with_pii | customer | 0.99 | redact_free_text | — | auto_proposed | Il testo libero contiene pattern PII e nomi noti; richiede futura redaction multipattern e revisione dei limiti regex. |
| crm | note_cliente | data_nota | PII-indiretta | technical_timestamp | customer | 0.90 | preserve_value | — | auto_proposed | Timestamp della nota collegata a un cliente tramite foreign key. |
| crm | ordini | ordine_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | ordini | cliente_id | PII-indiretta | internal_identifier | customer | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | ordini | data_ordine | PII-indiretta | financial_transaction | customer | 0.90 | preserve_value | — | auto_proposed | Attributo economico o operativo dell'ordine collegato a un cliente. |
| crm | ordini | importo | PII-indiretta | financial_transaction | customer | 0.90 | preserve_value | — | auto_proposed | Attributo economico o operativo dell'ordine collegato a un cliente. |
| crm | ordini | stato | PII-indiretta | financial_transaction | customer | 0.90 | preserve_value | — | auto_proposed | Attributo economico o operativo dell'ordine collegato a un cliente. |
| crm | referenti_commerciali | referente_id | PII-indiretta | internal_identifier | commercial_contact | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| crm | referenti_commerciali | nome_ref | PII-diretta | person_name | commercial_contact | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| crm | referenti_commerciali | email_ref | PII-diretta | email_address | commercial_contact | 0.98 | mask_email | commercial_contact_email | auto_proposed | Sintassi email rilevata sui valori e normalizzazione case-insensitive disponibile per i confronti. |
| crm | referenti_commerciali | telefono_ref | PII-diretta | phone_number | commercial_contact | 0.98 | mask_phone | commercial_contact_phone | auto_proposed | Struttura telefonica coerente rilevata nei valori, non soltanto nel nome della colonna. |
| hr | buste_paga | busta_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | buste_paga | dipendente_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | buste_paga | mese | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | buste_paga | anno | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | buste_paga | lordo | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | buste_paga | netto | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | buste_paga | iban_accredito | PII-diretta | italian_iban | employee | 0.99 | mask_iban | employee_iban | auto_proposed | Valori con struttura italiana e checksum IBAN valido, associati a conto o intestatario. |
| hr | dipendenti | dipendente_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | dipendenti | nome | PII-diretta | person_name | employee | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| hr | dipendenti | cognome | PII-diretta | person_name | employee | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| hr | dipendenti | cod_fisc | PII-diretta | italian_tax_code | employee | 0.99 | mask_tax_code | employee_tax_code | auto_proposed | Struttura di 16 caratteri e carattere di controllo validi, confermati dal profiling dei valori. |
| hr | dipendenti | email_aziendale | PII-diretta | email_address | employee | 0.98 | mask_email | employee_email | auto_proposed | Sintassi email rilevata sui valori e normalizzazione case-insensitive disponibile per i confronti. |
| hr | dipendenti | iban | PII-diretta | italian_iban | employee | 0.99 | mask_iban | employee_iban | auto_proposed | Valori con struttura italiana e checksum IBAN valido, associati a conto o intestatario. |
| hr | dipendenti | data_assunzione | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | dipendenti | reparto_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | formazione | corso_id | Non-PII | internal_identifier | not_applicable | 0.94 | preserve_value | — | auto_proposed | Chiave tecnica della struttura operativa, priva di collegamento diretto a una persona nel modello corrente. |
| hr | formazione | titolo | Non-PII | business_metadata | not_applicable | 0.92 | preserve_value | — | auto_proposed | Metadato del corso sintetico non riferito a una persona, escluso il docente trattato separatamente. |
| hr | formazione | docente | PII-diretta | person_name | external_person | 0.97 | mask_person_name | — | auto_proposed | Contesto personale e confronto con colonne note confermano valori compatibili con nomi o cognomi di persone. |
| hr | formazione | data_corso | Non-PII | business_metadata | not_applicable | 0.92 | preserve_value | — | auto_proposed | Metadato del corso sintetico non riferito a una persona, escluso il docente trattato separatamente. |
| hr | presenze | presenza_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | presenze | dipendente_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | presenze | data | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | presenze | ore | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | presenze | tipo | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | reparti | reparto_id | Non-PII | internal_identifier | not_applicable | 0.94 | preserve_value | — | auto_proposed | Chiave tecnica della struttura operativa, priva di collegamento diretto a una persona nel modello corrente. |
| hr | reparti | nome_reparto | Non-PII | business_metadata | not_applicable | 0.95 | preserve_value | — | auto_proposed | Metadato organizzativo del reparto privo di riferimento individuale. |
| hr | reparti | responsabile_id | PII-indiretta | internal_identifier | employee | 1.00 | preserve_technical_key | — | confirmed | Identificativo che collega logicamente il reparto al dipendente responsabile con match completo e nessun orfano, senza FK dichiarata. |
| hr | valutazioni | valutazione_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | valutazioni | dipendente_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | valutazioni | valutatore_id | PII-indiretta | internal_identifier | employee | 0.93 | preserve_technical_key | — | auto_proposed | Identificativo tecnico che abilita join verso record riferiti a una persona; non è significativo isolatamente ma consente collegamento. |
| hr | valutazioni | anno | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | valutazioni | punteggio | PII-indiretta | employment_information | employee | 0.92 | preserve_value | — | auto_proposed | Informazione professionale, retributiva, di presenza o valutazione associata a un dipendente. |
| hr | valutazioni | commento | PII-nascosta | free_text_with_pii | employee | 0.99 | redact_free_text | — | auto_proposed | Il testo libero contiene pattern PII e nomi noti; richiede futura redaction multipattern e revisione dei limiti regex. |

## Limiti

- La classificazione usa metadati, profiling sintetico, relazioni e regole contestuali; non sostituisce la conoscenza del data owner.
- Regex e confronto con nomi noti non garantiscono copertura completa della PII non strutturata.
- Le relazioni `logical_suspected` restano ipotesi e non vengono promosse automaticamente.
- Le masking rule sono proposte di governance e non sono ancora implementate.

## Responsabilità della revisione umana

Il data owner deve validare le colonne `Dubbio`, le relazioni sospette, il contesto degli identificativi e l'impatto analitico delle trasformazioni prima dell'uso in produzione.
