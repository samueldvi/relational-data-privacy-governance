CREATE TABLE IF NOT EXISTS crm.clienti (
    cliente_id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    cognome VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    telefono VARCHAR(30),
    cod_fisc VARCHAR(16) NOT NULL UNIQUE,
    data_nascita DATE,
    segmento VARCHAR(50),
    data_registrazione TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS crm.indirizzi (
    indirizzo_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    via VARCHAR(255) NOT NULL,
    cap VARCHAR(10),
    citta VARCHAR(100),
    provincia VARCHAR(10),
    CONSTRAINT fk_indirizzi_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES crm.clienti(cliente_id)
);

CREATE TABLE IF NOT EXISTS crm.contatti_extra (
    contatto_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    valore VARCHAR(255) NOT NULL,
    CONSTRAINT fk_contatti_extra_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES crm.clienti(cliente_id)
);

CREATE TABLE IF NOT EXISTS crm.ordini (
    ordine_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    data_ordine DATE NOT NULL,
    importo NUMERIC(12,2) NOT NULL,
    stato VARCHAR(30) NOT NULL,
    CONSTRAINT fk_ordini_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES crm.clienti(cliente_id)
);

CREATE TABLE IF NOT EXISTS crm.note_cliente (
    nota_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    testo TEXT NOT NULL,
    data_nota TIMESTAMP NOT NULL,
    CONSTRAINT fk_note_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES crm.clienti(cliente_id)
);

CREATE TABLE IF NOT EXISTS crm.campagne (
    campagna_id BIGSERIAL PRIMARY KEY,
    nome_campagna VARCHAR(150) NOT NULL,
    email_template TEXT NOT NULL,
    data_inizio DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS crm.consensi (
    consenso_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    tipo_consenso VARCHAR(50) NOT NULL,
    data_consenso TIMESTAMP NOT NULL,
    revocato BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_consensi_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES crm.clienti(cliente_id)
);

CREATE TABLE IF NOT EXISTS crm.referenti_commerciali (
    referente_id BIGSERIAL PRIMARY KEY,
    nome_ref VARCHAR(100) NOT NULL,
    email_ref VARCHAR(255) NOT NULL,
    telefono_ref VARCHAR(30)
);
