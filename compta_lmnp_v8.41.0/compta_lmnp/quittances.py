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
    UNIQUE (locataire_id, periode)
);
"""


def assurer_schema(conn: sqlite3.Connection) -> None:
    """Crée les tables si besoin — installations existantes comprises."""
    conn.executescript(SCHEMA)
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


def emettre(conn: sqlite3.Connection, *, locataire_id: int, periode: str,
            loyer: float | None = None, charges: float | None = None,
            date_paiement: str | None = None) -> dict:
    """Émet une quittance. Les montants viennent des écritures par défaut."""
    assurer_schema(conn)
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
    concurrentes = conn.execute(
        "SELECT q.numero, l.nom, l.id FROM quittance q "
        "JOIN locataire l ON l.id = q.locataire_id "
        "WHERE l.bien_id = ? AND q.periode = ?",
        (loc["bien_id"], periode)).fetchall()
    for numero, nom, autre_id in concurrentes:
        if autre_id == locataire_id:
            raise ValueError(
                f"Une quittance existe déjà pour {loc['nom']} en {periode} "
                f"(n° {numero:05d}). Une quittance atteste d'un paiement : "
                "en émettre deux pour le même mois créerait deux preuves du "
                "même encaissement.")
        raise ValueError(
            f"Le logement a déjà été quittancé pour {periode} : quittance "
            f"n° {numero:05d} au nom de {nom}. Le montant est lu dans les "
            "écritures du LOGEMENT ; en émettre une seconde attesterait "
            "deux fois le même encaissement.\n\n"
            "En colocation, indiquez le montant revenant à chacun dans les "
            "champs Loyer et Charges plutôt que de laisser le calcul "
            "automatique — la somme des quittances doit égaler ce qui a "
            "été encaissé.")

    if loyer is None or charges is None:
        auto = montants_depuis_ecritures(conn, loc["bien_id"], periode)
        loyer = auto["loyer"] if loyer is None else loyer
        charges = auto["charges"] if charges is None else charges
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

    numero = prochain_numero(conn)
    cur = conn.execute(
        "INSERT INTO quittance (numero, locataire_id, periode, "
        "date_emission, date_paiement, loyer, charges) VALUES (?,?,?,?,?,?,?)",
        (numero, locataire_id, periode,
         datetime.date.today().isoformat(), date_paiement or None,
         loyer, charges))
    conn.commit()
    return {"id": cur.lastrowid, "numero": numero, "periode": periode,
            "loyer": loyer, "charges": charges, "total": round(loyer + charges, 2),
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
        "SELECT q.*, l.nom AS locataire, l.date_entree, l.date_sortie, "
        "       l.bien_id AS bien_id, "
        "       b.libelle AS bien, b.adresse AS bien_adresse "
        "FROM quittance q JOIN locataire l ON l.id = q.locataire_id "
        "JOIN bien b ON b.id = l.bien_id WHERE q.id=?", (quittance_id,))
    if q is None:
        raise ValueError("Quittance introuvable.")
    exp = _ligne(conn, "SELECT nom, adresse FROM exploitant LIMIT 1")
    q["bailleur"] = exp or {"nom": "", "adresse": ""}
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
