# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Quittances de loyer — locataires, numérotation, génération.

Une quittance atteste qu'un loyer a été PAYÉ. Le bailleur doit la remettre
gratuitement au locataire qui la demande (loi n° 89-462 du 6 juillet 1989,
art. 21). Elle distingue obligatoirement le LOYER des CHARGES.

Ce module ne réinvente rien : il puise dans les écritures déjà saisies.
Une quittance n'est pas une déclaration, c'est le reflet d'un
encaissement — la produire depuis une saisie manuelle parallèle
introduirait un deuxième jeu de chiffres, et donc des divergences.

DONNÉES PERSONNELLES — note de conception
------------------------------------------
Une quittance a besoin du NOM du locataire, de l'adresse du logement, de
la période et des montants. Rien d'autre. La date et le lieu de naissance
ont existé un temps comme champs facultatifs : ils ont été RETIRÉS, parce
qu'un champ qui ne sert à rien finit par être rempli, et qu'une donnée
qu'on ne détient pas est une donnée qu'on n'a ni à protéger, ni à
justifier, ni à effacer sur demande.
"""
from __future__ import annotations

import datetime
import sqlite3

SCHEMA_QUITTANCE = """
CREATE TABLE IF NOT EXISTS quittance (
    id              INTEGER PRIMARY KEY,
    numero          INTEGER NOT NULL UNIQUE,   -- incrémental, sans trou
    locataire_id    INTEGER NOT NULL REFERENCES locataire(id),
    periode         TEXT    NOT NULL,          -- AAAA-MM
    date_emission   TEXT    NOT NULL,
    date_paiement   TEXT,
    loyer           REAL    NOT NULL,
    charges         REAL    NOT NULL DEFAULT 0,
    -- Pas d'UNIQUE (locataire_id, periode) : l'article 21 de la loi de
    -- 1989 distingue le REÇU d'un paiement partiel de la QUITTANCE d'un
    -- mois soldé. Le second document remplace le premier sans l'effacer —
    -- tous deux ont circulé, tous deux gardent leur numéro. L'unicité
    -- porte donc sur (locataire, période, type), et `emettre` refuse le
    -- reste.
    type_document   TEXT    NOT NULL DEFAULT 'quittance',
    -- Identité FIGÉE à l'émission. Le document était reconstruit par
    -- jointure sur le référentiel courant : corriger le nom d'un locataire
    -- ou l'adresse d'un logement réécrivait tous les justificatifs déjà
    -- remis, sous leur numéro d'origine.
    nom_locataire     TEXT,
    adresse_logement  TEXT,
    bailleur_nom      TEXT,
    bailleur_adresse  TEXT,
    montant_du        REAL,
    UNIQUE (locataire_id, periode, type_document)
);
"""

SCHEMA = """
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
    -- Pas d'UNIQUE (locataire_id, periode) : l'article 21 de la loi de
    -- 1989 distingue le REÇU d'un paiement partiel de la QUITTANCE d'un
    -- mois soldé. Le second document remplace le premier sans l'effacer —
    -- tous deux ont circulé, tous deux gardent leur numéro. L'unicité
    -- porte donc sur (locataire, période, type), et `emettre` refuse le
    -- reste.
    type_document   TEXT    NOT NULL DEFAULT 'quittance',
    -- Identité FIGÉE à l'émission. Le document était reconstruit par
    -- jointure sur le référentiel courant : corriger le nom d'un locataire
    -- ou l'adresse d'un logement réécrivait tous les justificatifs déjà
    -- remis, sous leur numéro d'origine.
    nom_locataire     TEXT,
    adresse_logement  TEXT,
    bailleur_nom      TEXT,
    bailleur_adresse  TEXT,
    montant_du        REAL,
    UNIQUE (locataire_id, periode, type_document)
);
"""


COLONNES_DOCUMENT = ("type_document", "nom_locataire", "adresse_logement",
                     "bailleur_nom", "bailleur_adresse", "montant_du")


def _relacher_unicite_periode(conn: sqlite3.Connection) -> None:
    """Remplace l'ancienne unicité (locataire, période) par (locataire,
    période, type de document).

    Une contrainte d'unicité posée dans un CREATE TABLE ne s'altère pas :
    il faut reconstruire la table. Sans cela, un reçu de paiement partiel
    interdirait pour toujours la quittance du mois une fois celui-ci
    soldé — ce qui est exactement le défaut que la distinction des deux
    documents vient corriger.
    """
    try:
        index = conn.execute("PRAGMA index_list(quittance)").fetchall()
    except sqlite3.OperationalError:
        return                                   # table pas encore créée
    ancienne = False
    for ligne in index:
        nom, unique = ligne[1], ligne[2]
        if not unique or not nom.startswith("sqlite_autoindex"):
            continue
        colonnes = [r[2] for r in conn.execute(f"PRAGMA index_info('{nom}')")]
        if colonnes == ["locataire_id", "periode"]:
            ancienne = True
    if not ancienne:
        return
    colonnes_presentes = [r[1] for r in
                          conn.execute("PRAGMA table_info(quittance)")]
    communes = ", ".join(c for c in colonnes_presentes
                         if c != "type_document")
    conn.executescript(f"""
        PRAGMA foreign_keys=OFF;
        ALTER TABLE quittance RENAME TO quittance_ancienne;
        {SCHEMA_QUITTANCE}
        INSERT INTO quittance ({communes}, type_document)
            SELECT {communes}, 'quittance' FROM quittance_ancienne;
        DROP TABLE quittance_ancienne;
        PRAGMA foreign_keys=ON;
    """)
    conn.commit()


def _schema_a_jour(conn: sqlite3.Connection) -> bool:
    """Les tables et colonnes attendues sont-elles déjà là ?"""
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"locataire", "quittance"} <= tables:
            return False
        colonnes = {r[1] for r in conn.execute("PRAGMA table_info(quittance)")}
        if not set(COLONNES_DOCUMENT) <= colonnes:
            return False
        for ligne in conn.execute("PRAGMA index_list(quittance)"):
            if ligne[2] and ligne[1].startswith("sqlite_autoindex"):
                cols = [r[2] for r in
                        conn.execute(f"PRAGMA index_info('{ligne[1]}')")]
                if cols == ["locataire_id", "periode"]:
                    return False              # ancienne unicité à relâcher
    except sqlite3.Error:
        return False
    return True


def assurer_schema(conn: sqlite3.Connection) -> None:
    """Crée les tables si besoin — installations existantes comprises.

    N'ÉCRIT RIEN quand il n'y a rien à faire. `executescript` valide la
    transaction en cours avant d'exécuter son script : appelée depuis un
    simple lecteur — lister les quittances, calculer le prochain numéro —
    cette fonction validait donc ce que l'appelant avait écrit sans le
    vouloir. Un loyer de 800 € saisi en `commit=False` survivait au
    rollback qui suivait, uniquement parce qu'on avait lu des quittances
    entre-temps. Le contrat de composition était rompu pour tout appelant.
    """
    if _schema_a_jour(conn):
        return
    conn.executescript(SCHEMA)
    # Colonnes ajoutées après coup sur les bases déjà en service. Le
    # `CREATE TABLE IF NOT EXISTS` ci-dessus ne touche pas une table
    # existante : sans ces ALTER, un dossier créé avant cette version
    # continuerait de reconstruire ses quittances par jointure.
    _relacher_unicite_periode(conn)
    for colonne in COLONNES_DOCUMENT:
        try:
            defaut = (" NOT NULL DEFAULT 'quittance'"
                      if colonne == "type_document" else "")
            type_col = "REAL" if colonne == "montant_du" else "TEXT"
            conn.execute(f"ALTER TABLE quittance ADD COLUMN {colonne} "
                         f"{type_col}{defaut}")
        except sqlite3.OperationalError:
            pass                                    # colonne déjà présente
    conn.commit()


def _lignes(conn, sql: str, params: tuple = ()) -> list[dict]:
    """Résultats en dictionnaires, quelle que soit la row_factory.

    Le module ne suppose pas que l'appelant a réglé sqlite3.Row : un outil
    en ligne de commande ou un test ouvre souvent une connexion nue, et
    `dict(row)` échoue alors sans que la cause soit lisible.
    """
    cur = conn.execute(sql, params)
    colonnes = [c[0] for c in cur.description]
    return [dict(zip(colonnes, r)) for r in cur.fetchall()]


def _ligne(conn, sql: str, params: tuple = ()) -> dict | None:
    rows = _lignes(conn, sql, params)
    return rows[0] if rows else None


# ── Locataires ──────────────────────────────────────────────────────────────

def ajouter_locataire(conn: sqlite3.Connection, *, bien_id: int, nom: str,
                      date_entree: str, date_sortie: str | None = None,
                      loyer_mensuel: float | None = None,
                      charges_mensuelles: float = 0.0) -> int:
    assurer_schema(conn)
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Le nom du locataire est obligatoire.")
    if not conn.execute("SELECT 1 FROM bien WHERE id=?", (bien_id,)).fetchone():
        raise ValueError("Bien introuvable : créez-le d'abord dans la page "
                         "Immobilisations.")
    _valider_date(date_entree, "date d'entrée")
    if date_sortie:
        _valider_date(date_sortie, "date de sortie")
        if date_sortie < date_entree:
            raise ValueError("La date de sortie précède la date d'entrée.")
    cur = conn.execute(
        "INSERT INTO locataire (bien_id, nom, date_entree, date_sortie, "
        "loyer_mensuel, charges_mensuelles) VALUES (?,?,?,?,?,?)",
        (bien_id, nom, date_entree, date_sortie or None,
         loyer_mensuel, round(float(charges_mensuelles or 0), 2)))
    conn.commit()
    return cur.lastrowid


def _valider_date(valeur: str, quoi: str) -> None:
    try:
        datetime.date.fromisoformat(valeur)
    except (TypeError, ValueError):
        raise ValueError(f"La {quoi} doit être au format AAAA-MM-JJ "
                         f"(reçu : « {valeur} »).") from None


def locataires(conn: sqlite3.Connection) -> list[dict]:
    assurer_schema(conn)
    return _lignes(conn,
        "SELECT l.*, b.libelle AS bien, b.adresse AS bien_adresse "
        "FROM locataire l JOIN bien b ON b.id = l.bien_id "
        "ORDER BY COALESCE(l.date_sortie, '9999'), l.date_entree DESC")


def present_le(loc: dict, periode: str) -> bool:
    """Le locataire occupe-t-il le logement sur cette période (AAAA-MM) ?"""
    fin_mois = f"{periode}-31"
    if loc["date_entree"] > fin_mois:
        return False
    return not (loc.get("date_sortie") and loc["date_sortie"] < f"{periode}-01")


# ── Quittances ──────────────────────────────────────────────────────────────

def prochain_numero(conn: sqlite3.Connection) -> int:
    """Numérotation incrémentale et SANS TROU.

    Une quittance annulée ne libère pas son numéro : la suite doit rester
    continue pour rester vérifiable, comme la numérotation des écritures.
    """
    assurer_schema(conn)
    r = conn.execute("SELECT COALESCE(MAX(numero), 0) FROM quittance").fetchone()
    return r[0] + 1


def montants_depuis_ecritures(conn: sqlite3.Connection, bien_id: int,
                              periode: str) -> dict:
    """Loyer et charges ENCAISSÉS sur la période, lus dans les écritures.

    La quittance reflète la comptabilité plutôt qu'une saisie parallèle :
    deux jeux de chiffres finiraient par diverger, et c'est la quittance —
    remise à un tiers — qui ferait foi contre nous.
    """
    import gabarits as _g
    catalogue = _g.tous(conn)
    # Les deux branches appliquaient des règles opposées : celle du loyer
    # testait une nature en plus d'une clé littérale — condition inerte,
    # puisque la clé était déjà imposée — et celle des charges ne testait
    # aucune nature, si bien qu'un gabarit de charge DÉCAISSÉE pouvait
    # remonter dans une quittance, qui atteste par définition d'une somme
    # REÇUE. On sélectionne désormais des PRODUITS dans les deux cas.
    QUITTANCABLE_LOYER = ("loyer", "arriere_loyer", "complement_loyer")
    QUITTANCABLE_CHARGES = ("charges_locatives", "provision_charges",
                            "forfait_charges", "regularisation_charges")

    def produits(cles):
        return [t for t, g in catalogue.items()
                if t in cles and g.get("nature") == "produit"]

    types_loyer = produits(QUITTANCABLE_LOYER)
    types_charges = produits(QUITTANCABLE_CHARGES)

    def somme(types: list[str]) -> float:
        if not types:
            return 0.0
        ph = ",".join("?" * len(types))
        return round(conn.execute(
            f"SELECT COALESCE(SUM(montant), 0) FROM operation "
            f"WHERE COALESCE(annulee,0)=0 AND periode=? AND bien_id=? "
            f"AND type IN ({ph})",
            (periode, bien_id, *types)).fetchone()[0] or 0.0, 2)

    return {"loyer": somme(types_loyer), "charges": somme(types_charges)}


TOL = 0.005


def _montant_du(loc) -> float | None:
    """Loyer + charges DUS pour un mois, d'après la fiche du locataire."""
    loyer = loc.get("loyer_mensuel")
    if loyer is None:
        return None
    return round(float(loyer) + float(loc.get("charges_mensuelles") or 0), 2)


def _adresse_logement(bien) -> str:
    """Adresse postale du logement, ou chaîne vide.

    Le gabarit se rabattait sur le LIBELLÉ interne du bien — « Logement
    Alpha Fictif » — et le présentait comme l'adresse du logement. Un
    repli muet vaut mieux qu'une mention fausse : on rend vide, et
    l'émission le signale.
    """
    if not bien:
        return ""
    return (bien.get("adresse") or "").strip()


def _date_encaissement(conn, bien_id: int, periode: str) -> str | None:
    """Date du dernier encaissement de loyer de la période, si elle est
    connue — plutôt que de laisser la date de paiement vide alors que
    l'opération la porte."""
    r = conn.execute(
        "SELECT MAX(date_operation) FROM operation WHERE bien_id=? "
        "AND periode=? AND COALESCE(annulee,0)=0 AND type LIKE '%loyer%'",
        (bien_id, periode)).fetchone()
    return r[0] if r and r[0] else None


def emettre(conn: sqlite3.Connection, *, locataire_id: int, periode: str,
            loyer: float | None = None, charges: float | None = None,
            date_paiement: str | None = None, forcer: bool = False) -> dict:
    """Émet un justificatif de loyer. Les montants viennent des écritures
    par défaut ; `forcer` passe outre le rapprochement avec l'encaissement,
    pour les cas que le logiciel ne sait pas voir (paiement en espèces
    non encore saisi, par exemple)."""
    assurer_schema(conn)
    # VERROU D'ÉCRITURE AVANT TOUTE LECTURE DE CONTRÔLE. Deux demandes
    # parallèles franchissaient l'une et l'autre le contrôle « ce logement
    # a-t-il déjà été quittancé ? », puis émettaient chacune leur document :
    # 1 600 € attestés à des tiers pour 800 € encaissés. Le contrôle
    # séquentiel était juste ; c'est son contournement concurrent qui ne
    # l'était pas. La contrainte d'unicité, elle, ne porte pas sur le
    # logement et ne pouvait pas rattraper le coup.
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    loc = _ligne(conn, "SELECT * FROM locataire WHERE id=?", (locataire_id,))
    if loc is None:
        raise ValueError("Locataire introuvable.")
    # Le mois doit EXISTER : « 2026-00 » passait et s'imprimait
    # « décembre 2026 » (indice -1 dans la table des mois), « 2026-13 »
    # imprimait la période brute.
    mois_ok = False
    if len(periode or "") == 7 and periode[4] == "-":
        try:
            mois_ok = 1 <= int(periode[5:]) <= 12 and periode[:4].isdigit()
        except ValueError:
            mois_ok = False
    if not mois_ok:
        raise ValueError("La période doit être au format AAAA-MM, avec un "
                         f"mois de 01 à 12 (reçu : « {periode} »).")
    if not present_le(loc, periode):
        raise ValueError(
            f"{loc['nom']} n'occupe pas le logement en {periode} "
            f"(entrée le {loc['date_entree']}"
            + (f", sortie le {loc['date_sortie']}" if loc.get("date_sortie") else "")
            + "). Vérifiez la période ou les dates de présence.")
    # Le montant est lu PAR LOGEMENT, mais l'unicité ne portait que sur le
    # locataire : rien ne reliait les deux. En colocation — ou lors d'une
    # relocation en cours de mois — chaque occupant recevait une quittance
    # portant la TOTALITÉ du loyer encaissé. Deux documents opposables au
    # bailleur attestaient 1 600 € pour 800 € reçus, et chacun était
    # individuellement « conforme aux écritures ».
    # Documents DÉJÀ ÉMIS pour ce logement et cette période. L'unicité
    # portait sur le LOGEMENT : en colocation, ou lors d'une relocation en
    # cours de mois, le second occupant ne pouvait plus être quittancé —
    # alors même que le message d'erreur lui conseillait de ventiler. Le
    # parcours conseillé était donc refusé par le contrôle qui le
    # conseillait. Ce qui doit rester interdit, c'est d'attester DEUX FOIS
    # le même encaissement : on additionne donc ce qui a déjà été attesté
    # sur le logement, et on le compare à ce qui a été encaissé.
    deja = conn.execute(
        "SELECT q.numero, q.type_document, q.loyer, q.charges, l.nom, l.id "
        "FROM quittance q JOIN locataire l ON l.id = q.locataire_id "
        "WHERE l.bien_id = ? AND q.periode = ?",
        (loc["bien_id"], periode)).fetchall()
    encaisse = montants_depuis_ecritures(conn, loc["bien_id"], periode)
    if loyer is None or charges is None:
        # En automatique, on ne propose que ce qui RESTE à attester.
        reste_loyer = round(encaisse["loyer"] - sum(
            d[2] for d in deja if d[1] == "quittance"), 2)
        reste_charges = round(encaisse["charges"] - sum(
            d[3] for d in deja if d[1] == "quittance"), 2)
        loyer = max(0.0, reste_loyer) if loyer is None else loyer
        charges = max(0.0, reste_charges) if charges is None else charges
    loyer, charges = round(float(loyer), 2), round(float(charges or 0), 2)
    # Aucun montant négatif sur un document remis à un tiers : le test
    # était un ET, si bien qu'un loyer de −100 accompagné de 50 € de
    # charges produisait une quittance à −50 €.
    if loyer < 0 or charges < 0:
        raise ValueError(
            "Une quittance atteste d'une somme REÇUE : les montants ne "
            "peuvent pas être négatifs. Pour un trop-perçu à restituer, "
            "saisissez une « Restitution de charges au locataire » dans la "
            "page Saisie, puis émettez la quittance du montant net.")
    if date_paiement:
        _valider_date(date_paiement, "date de paiement")
    if loyer <= 0 and charges <= 0:
        raise ValueError(
            f"Aucun encaissement trouvé pour {periode}. Une quittance "
            "atteste d'un paiement REÇU : saisissez d'abord le loyer dans "
            "la page Saisie, ou indiquez les montants à la main.")

    total = round(loyer + charges, 2)

    # ── Ce qui a DÉJÀ été attesté pour ce logement ne peut pas l'être deux
    #    fois. C'est la seule interdiction qui protège réellement le
    #    bailleur : deux documents opposables pour un même encaissement.
    attesté = round(sum(d[2] + d[3] for d in deja
                        if d[1] == "quittance"), 2)
    total_encaisse = round(encaisse["loyer"] + encaisse["charges"], 2)
    if (not forcer and attesté > TOL
            and round(attesté + total, 2) > total_encaisse + TOL):
        detail = ", ".join(f"n° {d[0]:05d} au nom de {d[4]} ({d[2] + d[3]:.2f} €)"
                           for d in deja if d[1] == "quittance")
        raise ValueError(
            f"Le logement a déjà été quittancé pour {periode} à hauteur de "
            f"{attesté:.2f} € ({detail}), et {total_encaisse:.2f} € ont été "
            f"encaissés. Ajouter {total:.2f} € attesterait plus que ce qui a "
            "été reçu.\n\n"
            "En colocation, la somme des quittances doit égaler ce qui a été "
            "encaissé : indiquez la part de chacun dans les champs Loyer et "
            "Charges.")

    # ── Attester plus que ce qui est encaissé, ventilation comprise ──────
    #    Seul le TOTAL était comparé, et seulement à la consultation : une
    #    attestation pouvait être émise sans le moindre encaissement, ou
    #    transformer 80 € de charges en loyer sans que rien ne le signale.
    #    L'article 21 de la loi de 1989 impose précisément cette
    #    ventilation, qui est ce que le locataire fera valoir.
    if not forcer:
        manque = []
        if loyer > round(encaisse["loyer"] - sum(
                d[2] for d in deja if d[1] == "quittance"), 2) + TOL:
            manque.append(f"loyer attesté {loyer:.2f} € pour "
                          f"{encaisse['loyer']:.2f} € encaissé(s)")
        if charges > round(encaisse["charges"] - sum(
                d[3] for d in deja if d[1] == "quittance"), 2) + TOL:
            manque.append(f"charges attestées {charges:.2f} € pour "
                          f"{encaisse['charges']:.2f} € encaissée(s)")
        if manque:
            raise ValueError(
                "Ce document attesterait plus que ce qui a été encaissé : "
                + " ; ".join(manque) + ". Une quittance atteste d'une somme "
                "REÇUE, et sa ventilation entre loyer et charges est celle "
                "que le locataire fera valoir. Saisissez d'abord "
                "l'encaissement dans la page Saisie, ou corrigez les "
                "montants.")

    # ── Reçu partiel ou quittance ? ─────────────────────────────────────
    #    Un paiement partiel produisait une QUITTANCE de loyer, titre qui
    #    solde le mois — puis le solde payé ensuite ne pouvait plus être
    #    attesté du tout. L'article 21 distingue expressément le reçu.
    du = _montant_du(loc)
    type_document = "quittance"
    if du is not None and round(attesté + total, 2) < round(du, 2) - TOL:
        type_document = "recu"
    existant = next((d for d in deja
                     if d[5] == locataire_id and d[1] == type_document), None)
    if existant:
        raise ValueError(
            f"Un document de ce type existe déjà pour {loc['nom']} en "
            f"{periode} (n° {existant[0]:05d}). En émettre un second "
            "créerait deux preuves du même encaissement.")

    numero = prochain_numero(conn)
    bien = _ligne(conn, "SELECT * FROM bien WHERE id=?", (loc["bien_id"],))
    exploitant = _ligne(conn, "SELECT * FROM exploitant ORDER BY id LIMIT 1")
    cur = conn.execute(
        "INSERT INTO quittance (numero, locataire_id, periode, "
        "date_emission, date_paiement, loyer, charges, type_document, "
        "nom_locataire, adresse_logement, bailleur_nom, bailleur_adresse, "
        "montant_du) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (numero, locataire_id, periode,
         datetime.date.today().isoformat(),
         date_paiement or _date_encaissement(conn, loc["bien_id"], periode),
         loyer, charges, type_document, loc["nom"],
         _adresse_logement(bien), (exploitant or {}).get("nom"),
         (exploitant or {}).get("adresse"), du))
    conn.commit()
    return {"id": cur.lastrowid, "numero": numero, "periode": periode,
            "loyer": loyer, "charges": charges, "total": total,
            "type_document": type_document,
            "reste_du": (round(du - attesté - total, 2)
                         if du is not None else None),
            "locataire": loc["nom"]}


def lister(conn: sqlite3.Connection, annee: int | None = None) -> list[dict]:
    assurer_schema(conn)
    # Jointures EXTERNES : avec des jointures internes, la suppression
    # d'un bien ou d'un locataire faisait disparaître ses quittances de la
    # liste — alors que leurs numéros restaient consommés et que les
    # documents circulaient chez des tiers. Un trou dans une numérotation
    # que le logiciel garantit continue doit se VOIR, pas s'effacer.
    sql = ("SELECT q.*, COALESCE(l.nom, '(locataire supprimé)') AS locataire, "
           "COALESCE(b.libelle, '(logement supprimé)') AS bien "
           "FROM quittance q LEFT JOIN locataire l ON l.id = q.locataire_id "
           "LEFT JOIN bien b ON b.id = l.bien_id ")
    params: tuple = ()
    if annee:
        sql += "WHERE q.periode LIKE ? "
        params = (f"{annee}-%",)
    return _lignes(conn, sql + "ORDER BY q.numero DESC", params)


def detail(conn: sqlite3.Connection, quittance_id: int) -> dict:
    """Tout ce qu'il faut pour imprimer une quittance conforme."""
    assurer_schema(conn)
    q = _ligne(conn,
        "SELECT q.*, l.nom AS locataire, l.nom AS locataire_actuel, "
        "       l.date_entree, l.date_sortie, l.bien_id AS bien_id, "
        "       b.libelle AS bien, b.adresse AS bien_adresse, "
        "       b.adresse AS bien_adresse_actuelle "
        "FROM quittance q JOIN locataire l ON l.id = q.locataire_id "
        "JOIN bien b ON b.id = l.bien_id WHERE q.id=?", (quittance_id,))
    if q is None:
        raise ValueError("Quittance introuvable.")
    # L'IDENTITÉ FIGÉE prime sur le référentiel courant. Le document était
    # entièrement reconstruit par jointure : corriger le nom d'un locataire
    # ou l'adresse d'un logement réécrivait tous les justificatifs déjà
    # remis, sous leurs numéros d'origine, sans qu'aucune trace ne subsiste
    # de ce qui avait réellement circulé. Un justificatif se conserve, il
    # ne se recalcule pas.
    exp = _ligne(conn, "SELECT nom, adresse FROM exploitant LIMIT 1")
    q["bailleur"] = {
        "nom": q.get("bailleur_nom") or (exp or {}).get("nom") or "",
        "adresse": q.get("bailleur_adresse") or (exp or {}).get("adresse") or "",
    }
    if q.get("nom_locataire"):
        q["locataire"] = q["nom_locataire"]
    if q.get("adresse_logement"):
        q["bien_adresse"] = q["adresse_logement"]
    # Le référentiel a-t-il changé depuis l'émission ? Le dire, plutôt que
    # de laisser deux versions coexister en silence.
    q["referentiel_modifie"] = [
        libelle for libelle, fige, courant in (
            ("locataire", q.get("nom_locataire"), q.get("locataire_actuel")),
            ("adresse du logement", q.get("adresse_logement"),
             q.get("bien_adresse_actuelle")))
        if fige and courant and fige != courant]
    q["type_document"] = q.get("type_document") or "quittance"
    q["titre_document"] = ("Reçu de paiement partiel"
                           if q["type_document"] == "recu"
                           else "Quittance de loyer")
    if q.get("montant_du") is not None:
        q["reste_du"] = round(float(q["montant_du"]) - q["loyer"]
                              - q["charges"], 2)
    q["total"] = round(q["loyer"] + q["charges"], 2)
    q["periode_lettres"] = _mois_en_lettres(q["periode"])
    # Les montants sont figés à l'émission. Si l'encaissement est annulé
    # ENSUITE — un chèque impayé, une contre-passation —, la quittance
    # continue d'attester une somme qui n'a jamais été perçue, et elle
    # reste imprimable à l'identique. On la confronte donc aux écritures À
    # CHAQUE lecture : le module promet que « la quittance reflète la
    # comptabilité », ce qui n'était vrai qu'à l'instant de l'émission.
    reel = montants_depuis_ecritures(conn, q["bien_id"], q["periode"]) \
        if q.get("bien_id") else None
    q["ecart_ecritures"] = None
    if reel is not None:
        encaisse = round(reel["loyer"] + reel["charges"], 2)
        if encaisse + 0.005 < q["total"]:
            q["ecart_ecritures"] = {
                "encaisse": encaisse, "atteste": q["total"],
                "message": (
                    f"Cette quittance atteste {q['total']:.2f} €, alors que "
                    f"les écritures de {q['periode_lettres']} n'en portent "
                    f"plus que {encaisse:.2f} €. Un encaissement a "
                    "probablement été annulé depuis l'émission. Une "
                    "quittance remise ne se corrige pas : établissez-en une "
                    "rectificative, ou réclamez la restitution de "
                    "l'originale.")}
    return q


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def _mois_en_lettres(periode: str) -> str:
    try:
        a, m = periode.split("-")
        return f"{MOIS[int(m) - 1]} {a}"
    except (ValueError, IndexError):
        return periode
