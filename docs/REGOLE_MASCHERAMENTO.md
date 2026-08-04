# Regole di masking

> Documento generato deterministicamente dalle configurazioni YAML. Nessun secret è incluso.

## Principi

Le pseudonimizzazioni usano `HMAC-SHA-256(secret, namespace + ':' + valore_normalizzato)` e namespace distinti. I mapping di collisione esistono soltanto in memoria.

## Consistency group

| Gruppo | Dominio | Soggetto | Namespace | Normalizzazione | Formato | Colonne |
| --- | --- | --- | --- | --- | --- | --- |
| customer_tax_code | italian_tax_code | customer | `tax_code.customer.v1` | trim_remove_spaces_uppercase | italian_tax_code_16_with_check_character | billing.sconti.cod_rif, crm.clienti.cod_fisc |
| employee_tax_code | italian_tax_code | employee | `tax_code.employee.v1` | trim_remove_spaces_uppercase | italian_tax_code_16_with_check_character | hr.dipendenti.cod_fisc |
| customer_email | email_address | customer | `email.customer.v1` | trim_lowercase | u_token@example.test | billing.pagamenti.rif_esterno, billing.solleciti.destinatario_email, crm.clienti.email |
| employee_email | email_address | employee | `email.employee.v1` | trim_lowercase | u_token@example.test | hr.dipendenti.email_aziendale |
| customer_iban | italian_iban | bank_account_holder | `iban.customer.v1` | remove_spaces_uppercase | italian_iban_27_non_routable | billing.coordinate_bancarie.iban |
| employee_iban | italian_iban | employee | `iban.employee.v1` | remove_spaces_uppercase | italian_iban_27_non_routable | hr.buste_paga.iban_accredito, hr.dipendenti.iban |
| customer_phone | phone_number | customer | `phone.customer.v1` | international_digits_with_plus | +39_000_seven_digits | crm.clienti.telefono |
| commercial_contact_email | email_address | commercial_contact | `email.commercial_contact.v1` | trim_lowercase | u_token@example.test | crm.referenti_commerciali.email_ref |
| commercial_contact_phone | phone_number | commercial_contact | `phone.commercial_contact.v1` | international_digits_with_plus | +39_000_seven_digits | crm.referenti_commerciali.telefono_ref |

## Regole

### `mask_person_name`

- **Scopo e input:** domini `person_name`; trasformazione `deterministic_pseudonymization`.
- **Normalizzazione:** `trim_collapse_spaces_casefold`.
- **Algoritmo:** `HMAC-SHA-256`.
- **Output:** `synthetic_token_per_name_token`; esempio sintetico: `[REDACTED_NAME] → Persona_token`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Preserva il numero di token ma non distribuzione o fonetica dei nomi.
- **Limiti:** Non preserva genere, origine linguistica o omonimie semantiche.

### `mask_email`

- **Scopo e input:** domini `email_address`; trasformazione `deterministic_pseudonymization`.
- **Normalizzazione:** `trim_lowercase`.
- **Algoritmo:** `HMAC-SHA-256`.
- **Output:** `u_token@example.test`; esempio sintetico: `u***@example.test → u_token@example.test`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Preserva uguaglianza e join nel consistency group, non il dominio originale.
- **Limiti:** Non preserva alias, provider o struttura della parte locale.

### `mask_phone`

- **Scopo e input:** domini `phone_number`; trasformazione `deterministic_pseudonymization`.
- **Normalizzazione:** `international_digits_with_plus`.
- **Algoritmo:** `HMAC-SHA-256`.
- **Output:** `+39 000 seven_digits`; esempio sintetico: `+39******001 → +39 000 0000001`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Preserva uguaglianza nel gruppo ma non prefisso geografico reale.
- **Limiti:** Il prefisso 000 è deliberatamente sintetico e non instradabile.

### `mask_tax_code`

- **Scopo e input:** domini `italian_tax_code`; trasformazione `deterministic_format_preserving_pseudonymization`.
- **Normalizzazione:** `trim_remove_spaces_uppercase`.
- **Algoritmo:** `HMAC-SHA-256_with_check_character`.
- **Output:** `sixteen_alphanumeric_characters`; esempio sintetico: `ABCDEF********** → QWERTY00A01Z000R`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Preserva formato, validità formale e uguaglianza nel gruppo.
- **Limiti:** Non preserva i componenti anagrafici codificati nell'originale.

### `mask_iban`

- **Scopo e input:** domini `italian_iban`; trasformazione `deterministic_format_preserving_pseudonymization`.
- **Normalizzazione:** `remove_spaces_uppercase`.
- **Algoritmo:** `HMAC-SHA-256_with_MOD-97`.
- **Output:** `IT_check_CIN_00000_00000_account`; esempio sintetico: `IT************************* → ITxxX0000000000xxxxxxxxxxxx`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Preserva formato, checksum e uguaglianza nel gruppo.
- **Limiti:** ABI e CAB 00000 rendono intenzionalmente non instradabile l'output.

### `shift_birth_date`

- **Scopo e input:** domini `birth_date`; trasformazione `bounded_deterministic_shift`.
- **Normalizzazione:** `ISO_date`.
- **Algoritmo:** `HMAC-SHA-256_offset_modulo_61`.
- **Output:** `date_within_plus_or_minus_30_days`; esempio sintetico: `1980-**-** → data entro ±30 giorni`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `reject`.
- **Collisioni:** `not_applicable`.
- **Impatto analitico:** Mantiene approssimativamente età e coorti, non il giorno esatto.
- **Limiti:** L'ordinamento tra persone con date vicine può cambiare.

### `redact_free_text`

- **Scopo e input:** domini `free_text_with_pii`; trasformazione `deterministic_multipattern_redaction`.
- **Normalizzazione:** `non_destructive`.
- **Algoritmo:** `regex_and_explicit_known_name_dictionary`.
- **Output:** `standard_redaction_markers`; esempio sintetico: `Contatto sintetico → [REDACTED_EMAIL]`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `not_applicable`.
- **Impatto analitico:** Preserva testo non sensibile ma rimuove contenuti identificativi rilevati.
- **Limiti:** Regex e dizionari non garantiscono copertura completa senza strumenti NER.

### `preserve_technical_key`

- **Scopo e input:** domini `internal_identifier`; trasformazione `approved_identity`.
- **Normalizzazione:** `none`.
- **Algoritmo:** `identity_after_registry_authorization`.
- **Output:** `unchanged`; esempio sintetico: `1001 → 1001`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `not_applicable`.
- **Impatto analitico:** Preserva integralmente join e integrità referenziale.
- **Limiti:** Applicabile solo alle colonne approvate esplicitamente nel registry.

### `preserve_value`

- **Scopo e input:** domini `aggregate_metric, business_metadata, consent_information, employment_information, financial_transaction, geographic_information, internal_identifier, technical_timestamp`; trasformazione `identity`.
- **Normalizzazione:** `none`.
- **Algoritmo:** `identity`.
- **Output:** `unchanged`; esempio sintetico: `aggregato → aggregato`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `not_applicable`.
- **Impatto analitico:** Nessun impatto analitico sul valore.
- **Limiti:** La classificazione e il contesto devono essere validati prima dell'esecuzione.

### `review_before_masking`

- **Scopo e input:** domini `bank_reference`; trasformazione `blocking_control`.
- **Normalizzazione:** `none`.
- **Algoritmo:** `raise_controlled_error`.
- **Output:** `no_output`; esempio sintetico: `valore ambiguo → esecuzione bloccata`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `block_for_non_null` / `block`.
- **Collisioni:** `not_applicable`.
- **Impatto analitico:** Impedisce trasformazioni non approvate.
- **Limiti:** Richiede decisione esplicita del data owner.

### `mask_contact_value`

- **Scopo e input:** domini `contact_value`; trasformazione `conditional_deterministic_pseudonymization`.
- **Normalizzazione:** `based_on_contact_type`.
- **Algoritmo:** `HMAC-SHA-256`.
- **Output:** `email_or_phone_synthetic_format`; esempio sintetico: `contatto sintetico → formato email o telefono sintetico`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Preserva il tipo di contatto e l'uguaglianza nel relativo namespace.
- **Limiti:** Richiede il discriminante tipo della stessa riga.

### `mask_postal_address`

- **Scopo e input:** domini `postal_address`; trasformazione `deterministic_pseudonymization`.
- **Normalizzazione:** `trim_collapse_spaces_casefold`.
- **Algoritmo:** `HMAC-SHA-256`.
- **Output:** `synthetic_address_token`; esempio sintetico: `[REDACTED_ADDRESS] → Indirizzo sintetico token`.
- **Determinismo e namespace:** deterministico=true; il namespace è fornito dal consistency group o dal contesto del soggetto.
- **NULL e stringhe vuote:** `preserve` / `preserve`.
- **Collisioni:** `deterministic_counter_retry_sorted_inputs`.
- **Impatto analitico:** Non preserva geografia o struttura civica dell'indirizzo.
- **Limiti:** Componenti geografiche indirette seguono regole separate nel registry.

## Trasferimento concettuale verso Informatica

Le configurazioni locali rappresentano concetti di dominio, regola e coerenza cross-tabella trasferibili a una piattaforma enterprise. Nomi, disponibilità e comportamento delle funzioni specifiche di Informatica Data Privacy Management dovranno essere verificati quando la licenza sarà disponibile; questo documento non attribuisce funzionalità non osservate.
