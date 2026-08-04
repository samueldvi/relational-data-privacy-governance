CREATE TABLE IF NOT EXISTS billing.fatture (
    fattura_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    numero_fattura VARCHAR(50) NOT NULL UNIQUE,
    data_emissione DATE NOT NULL,
    importo NUMERIC(12,2) NOT NULL CHECK (importo >= 0),
    iva NUMERIC(5,2) NOT NULL CHECK (iva >= 0),
    stato VARCHAR(30) NOT NULL
);

-- billing.fatture.cliente_id e' intenzionalmente una relazione logica
-- cross-schema verso crm.clienti.cliente_id, non una FK dichiarata.

CREATE TABLE IF NOT EXISTS billing.pagamenti (
    pagamento_id BIGSERIAL PRIMARY KEY,
    fattura_id BIGINT NOT NULL,
    data_pagamento DATE NOT NULL,
    importo_pagato NUMERIC(12,2) NOT NULL CHECK (importo_pagato >= 0),
    metodo VARCHAR(30) NOT NULL,
    riferimento_bancario VARCHAR(100),
    rif_esterno VARCHAR(255),
    CONSTRAINT fk_pagamenti_fattura
        FOREIGN KEY (fattura_id)
        REFERENCES billing.fatture(fattura_id)
);

CREATE TABLE IF NOT EXISTS billing.coordinate_bancarie (
    coordinata_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    iban VARCHAR(27) NOT NULL UNIQUE,
    intestatario VARCHAR(200) NOT NULL,
    banca VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS billing.solleciti (
    sollecito_id BIGSERIAL PRIMARY KEY,
    fattura_id BIGINT NOT NULL,
    data_invio DATE NOT NULL,
    destinatario_email VARCHAR(255) NOT NULL,
    testo_sollecito TEXT NOT NULL,
    CONSTRAINT fk_solleciti_fattura
        FOREIGN KEY (fattura_id)
        REFERENCES billing.fatture(fattura_id)
);

CREATE TABLE IF NOT EXISTS billing.sconti (
    sconto_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    codice_sconto VARCHAR(50) NOT NULL UNIQUE,
    percentuale NUMERIC(5,2) NOT NULL CHECK (percentuale BETWEEN 0 AND 100),
    data_scadenza DATE,
    cod_rif VARCHAR(16)
);

CREATE TABLE IF NOT EXISTS billing.report_mensili (
    report_id BIGSERIAL PRIMARY KEY,
    mese SMALLINT NOT NULL CHECK (mese BETWEEN 1 AND 12),
    anno SMALLINT NOT NULL CHECK (anno BETWEEN 2000 AND 2200),
    totale_fatturato NUMERIC(14,2) NOT NULL CHECK (totale_fatturato >= 0),
    totale_incassato NUMERIC(14,2) NOT NULL CHECK (totale_incassato >= 0),
    CONSTRAINT uq_report_mensili_periodo UNIQUE (mese, anno)
);
