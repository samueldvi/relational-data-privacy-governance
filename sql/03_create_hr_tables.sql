CREATE TABLE IF NOT EXISTS hr.reparti (
    reparto_id BIGSERIAL PRIMARY KEY,
    nome_reparto VARCHAR(100) NOT NULL UNIQUE,
    responsabile_id BIGINT
);

CREATE TABLE IF NOT EXISTS hr.dipendenti (
    dipendente_id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    cognome VARCHAR(100) NOT NULL,
    cod_fisc VARCHAR(16) NOT NULL UNIQUE,
    email_aziendale VARCHAR(255) NOT NULL UNIQUE,
    iban VARCHAR(27) NOT NULL,
    data_assunzione DATE NOT NULL,
    reparto_id BIGINT NOT NULL,
    CONSTRAINT fk_dipendenti_reparto
        FOREIGN KEY (reparto_id)
        REFERENCES hr.reparti(reparto_id)
);

-- hr.reparti.responsabile_id e' intenzionalmente una relazione logica verso
-- hr.dipendenti.dipendente_id e non deve diventare un constraint dichiarato.

CREATE TABLE IF NOT EXISTS hr.buste_paga (
    busta_id BIGSERIAL PRIMARY KEY,
    dipendente_id BIGINT NOT NULL,
    mese SMALLINT NOT NULL CHECK (mese BETWEEN 1 AND 12),
    anno SMALLINT NOT NULL CHECK (anno BETWEEN 2000 AND 2200),
    lordo NUMERIC(12,2) NOT NULL CHECK (lordo >= 0),
    netto NUMERIC(12,2) NOT NULL CHECK (netto >= 0),
    iban_accredito VARCHAR(27) NOT NULL,
    CONSTRAINT fk_buste_paga_dipendente
        FOREIGN KEY (dipendente_id)
        REFERENCES hr.dipendenti(dipendente_id),
    CONSTRAINT uq_buste_paga_periodo UNIQUE (dipendente_id, mese, anno)
);

CREATE TABLE IF NOT EXISTS hr.presenze (
    presenza_id BIGSERIAL PRIMARY KEY,
    dipendente_id BIGINT NOT NULL,
    data DATE NOT NULL,
    ore NUMERIC(4,2) NOT NULL CHECK (ore BETWEEN 0 AND 24),
    tipo VARCHAR(30) NOT NULL,
    CONSTRAINT fk_presenze_dipendente
        FOREIGN KEY (dipendente_id)
        REFERENCES hr.dipendenti(dipendente_id),
    CONSTRAINT uq_presenze_giorno UNIQUE (dipendente_id, data)
);

CREATE TABLE IF NOT EXISTS hr.valutazioni (
    valutazione_id BIGSERIAL PRIMARY KEY,
    dipendente_id BIGINT NOT NULL,
    valutatore_id BIGINT NOT NULL,
    anno SMALLINT NOT NULL CHECK (anno BETWEEN 2000 AND 2200),
    punteggio NUMERIC(3,1) NOT NULL CHECK (punteggio BETWEEN 0 AND 10),
    commento TEXT,
    CONSTRAINT fk_valutazioni_dipendente
        FOREIGN KEY (dipendente_id)
        REFERENCES hr.dipendenti(dipendente_id),
    CONSTRAINT fk_valutazioni_valutatore
        FOREIGN KEY (valutatore_id)
        REFERENCES hr.dipendenti(dipendente_id)
);

CREATE TABLE IF NOT EXISTS hr.formazione (
    corso_id BIGSERIAL PRIMARY KEY,
    titolo VARCHAR(200) NOT NULL,
    docente VARCHAR(200) NOT NULL,
    data_corso DATE NOT NULL
);
