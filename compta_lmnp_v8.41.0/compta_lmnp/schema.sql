-- ============================================================================
-- Schéma SQLite — Compta LMNP au réel + FEC  (jalon J1)
-- Calé sur la mécanique des logiciels du marché : 4 journaux, contrepartie trésorerie = 108000.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- --- Référentiels ----------------------------------------------------------

CREATE TABLE exploitant (
    id      INTEGER PRIMARY KEY,
    nom     TEXT    NOT NULL,
    siren   TEXT    NOT NULL,
    adresse TEXT
);

CREATE TABLE bien (
    id                  INTEGER PRIMARY KEY,
    exploitant_id       INTEGER NOT NULL REFERENCES exploitant(id),
    libelle             TEXT    NOT NULL,
    adresse             TEXT,
    date_acquisition    TEXT,                 -- AAAA-MM-JJ
    prix_total          REAL,
    quote_part_terrain  REAL                  -- ex. 0.073504
);

CREATE TABLE journal (
    code    TEXT PRIMARY KEY,                 -- AN, AC, BQ, OD
    libelle TEXT NOT NULL
);

CREATE TABLE compte (
    numero  TEXT PRIMARY KEY,                 -- ex. 108000
    libelle TEXT NOT NULL,
    type    TEXT NOT NULL CHECK (type IN
              ('actif','passif','charge','produit','amortissement','attente')),
    classe  INTEGER NOT NULL                  -- 1er chiffre du compte
);

-- --- Immobilisations / composants ------------------------------------------

CREATE TABLE composant (
    id                INTEGER PRIMARY KEY,
    bien_id           INTEGER NOT NULL REFERENCES bien(id),
    code_immo         TEXT    UNIQUE,         -- réf. pièce des logiciels du marché (MODYDW, MFGTAG…)
    libelle           TEXT    NOT NULL,
    categorie         TEXT,
    valeur_brute      REAL    NOT NULL,
    duree_annees      INTEGER,                -- NULL = non amortissable (terrain)
    date_mise_service TEXT,                   -- AAAA-MM-JJ
    compte_immo       TEXT    REFERENCES compte(numero),
    compte_amort      TEXT    REFERENCES compte(numero),
    amortissable      INTEGER NOT NULL DEFAULT 1 CHECK (amortissable IN (0,1))
);

-- --- Comptabilité ----------------------------------------------------------

CREATE TABLE exercice (
    annee              INTEGER PRIMARY KEY,
    date_debut         TEXT NOT NULL,
    date_fin           TEXT NOT NULL,
    statut             TEXT NOT NULL DEFAULT 'ouvert'
                            CHECK (statut IN ('ouvert','clos')),
    resultat_comptable REAL,
    resultat_fiscal    REAL
);

CREATE TABLE ecriture (
    id              INTEGER PRIMARY KEY,
    journal_code    TEXT    NOT NULL REFERENCES journal(code),
    ecriture_num    INTEGER NOT NULL,
    ecriture_date   TEXT    NOT NULL,         -- AAAA-MM-JJ
    exercice_annee  INTEGER NOT NULL REFERENCES exercice(annee),
    piece_ref       TEXT,
    piece_date      TEXT,
    libelle         TEXT,
    valid_date      TEXT,
    UNIQUE (exercice_annee, ecriture_num)
);

CREATE TABLE ligne (
    id            INTEGER PRIMARY KEY,
    ecriture_id   INTEGER NOT NULL REFERENCES ecriture(id) ON DELETE CASCADE,
    compte_num    TEXT    NOT NULL REFERENCES compte(numero),
    comp_aux_num  TEXT    DEFAULT '',
    comp_aux_lib  TEXT    DEFAULT '',
    libelle       TEXT,
    debit         REAL    NOT NULL DEFAULT 0,
    credit        REAL    NOT NULL DEFAULT 0,
    ecriture_let  TEXT    DEFAULT '',
    date_let      TEXT    DEFAULT '',
    montant_devise TEXT   DEFAULT '',
    idevise       TEXT    DEFAULT '',
    CHECK (debit >= 0 AND credit >= 0),
    CHECK (NOT (debit > 0 AND credit > 0))    -- une ligne : débit XOR crédit
);

-- --- Couche événement métier (saisie par gabarits) -------------------------
-- Une opération = un fait de gestion (loyer, charge, acquisition…). Elle PORTE
-- l'intention (type, période, tiers) que l'écriture comptable seule ignore.
-- C'est cette couche qui rend possibles les contrôles de cohérence.
CREATE TABLE operation (
    id             INTEGER PRIMARY KEY,
    exercice_annee INTEGER NOT NULL REFERENCES exercice(annee),
    type           TEXT    NOT NULL,          -- clé de gabarit (loyer, charge_copro…)
    bien_id        INTEGER REFERENCES bien(id),
    tiers          TEXT    DEFAULT '',
    periode        TEXT,                       -- 'AAAA-MM' (mensuel) ou 'AAAA' (annuel)
    date_operation TEXT    NOT NULL,           -- AAAA-MM-JJ
    montant        REAL    NOT NULL CHECK (montant >= 0),
    annulee        INTEGER NOT NULL DEFAULT 0,       -- 1 = contre-passée
    libelle        TEXT,
    ecriture_id    INTEGER REFERENCES ecriture(id),
    source         TEXT    NOT NULL DEFAULT 'saisie'  -- saisie | import_bancaire
);

-- --- Plan d'amortissement (trace par composant et par exercice) ------------
CREATE TABLE plan_amortissement (
    id             INTEGER PRIMARY KEY,
    composant_id   INTEGER NOT NULL REFERENCES composant(id),
    exercice_annee INTEGER NOT NULL REFERENCES exercice(annee),
    dotation       REAL NOT NULL,
    cumul_fin      REAL NOT NULL,
    vnc_fin        REAL NOT NULL,
    UNIQUE (composant_id, exercice_annee)
);

-- --- Suivi fiscal (deux files DISTINCTES, jamais cumulées) ------------------

-- Article 39 C : report d'amortissement, SANS limite de durée.
CREATE TABLE suivi_39c (
    exercice_annee    INTEGER PRIMARY KEY REFERENCES exercice(annee),
    plafond_deductible REAL,                  -- loyers - charges (hors DAA)
    dotation_exercice  REAL,
    stock_ouverture    REAL NOT NULL DEFAULT 0,
    report_annee       REAL NOT NULL DEFAULT 0,
    utilisation_annee  REAL NOT NULL DEFAULT 0,
    stock_cloture      REAL NOT NULL DEFAULT 0
);

-- Déficit LMNP : imputable sur bénéfices de même nature, PÉREMPTION à 10 ans.
CREATE TABLE deficit_lmnp (
    id               INTEGER PRIMARY KEY,
    annee_origine    INTEGER NOT NULL,
    montant_initial  REAL    NOT NULL,
    solde            REAL    NOT NULL,        -- restant à imputer
    annee_expiration INTEGER NOT NULL         -- annee_origine + 10
);

-- --- Vues ------------------------------------------------------------------

-- Reconstitution des 18 colonnes du FEC par jointure.
-- Trace complète de la clôture (exploitée par la liasse fiscale).
-- NB : fiscal.cloturer la crée aussi à la volée (migration des bases antérieures).
CREATE TABLE IF NOT EXISTS cloture_fiscale (
    exercice_annee   INTEGER PRIMARY KEY REFERENCES exercice(annee),
    retraitements    REAL NOT NULL DEFAULT 0,
    impute_deficits  REAL NOT NULL DEFAULT 0,
    deficit_cree     REAL,
    revenu_imposable REAL NOT NULL DEFAULT 0
);

CREATE VIEW v_fec AS
SELECT
    e.journal_code                    AS JournalCode,
    j.libelle                         AS JournalLib,
    e.ecriture_num                    AS EcritureNum,
    REPLACE(e.ecriture_date,'-','')   AS EcritureDate,
    l.compte_num                      AS CompteNum,
    c.libelle                         AS CompteLib,
    l.comp_aux_num                    AS CompAuxNum,
    l.comp_aux_lib                    AS CompAuxLib,
    e.piece_ref                       AS PieceRef,
    REPLACE(COALESCE(e.piece_date,''),'-','') AS PieceDate,
    l.libelle                         AS EcritureLib,
    l.debit                           AS Debit,
    l.credit                          AS Credit,
    l.ecriture_let                    AS EcritureLet,
    REPLACE(COALESCE(l.date_let,''),'-','')   AS DateLet,
    REPLACE(COALESCE(e.valid_date,''),'-','') AS ValidDate,
    l.montant_devise                  AS Montantdevise,
    l.idevise                         AS Idevise
FROM ligne l
JOIN ecriture e ON e.id = l.ecriture_id
JOIN journal  j ON j.code = e.journal_code
JOIN compte   c ON c.numero = l.compte_num
ORDER BY e.exercice_annee, e.ecriture_num, l.id;

-- --- Quittances de loyer ----------------------------------------------------
-- Créées ici pour une base neuve, et à la volée par quittances.assurer_schema
-- pour une installation antérieure (palier de migration 6).
CREATE TABLE IF NOT EXISTS locataire (
    id              INTEGER PRIMARY KEY,
    bien_id         INTEGER NOT NULL REFERENCES bien(id),
    nom             TEXT    NOT NULL,
    date_entree     TEXT    NOT NULL,          -- AAAA-MM-JJ
    date_sortie     TEXT,                      -- NULL = en cours
    loyer_mensuel   REAL,
    charges_mensuelles REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quittance (
    id              INTEGER PRIMARY KEY,
    numero          INTEGER NOT NULL UNIQUE,   -- incrémental, sans trou
    locataire_id    INTEGER NOT NULL REFERENCES locataire(id),
    periode         TEXT    NOT NULL,          -- AAAA-MM
    date_emission   TEXT    NOT NULL,
    date_paiement   TEXT,
    loyer           REAL    NOT NULL,
    charges         REAL    NOT NULL DEFAULT 0,
    UNIQUE (locataire_id, periode)
);
