# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Charges récurrentes — modèles de charges qui reviennent à l'identique
(assurance PNO mensuelle, abonnement, charges de copropriété
trimestrielles…), générés en lot par le moteur `echeancier`.

Complète la duplication d'opération (`operations.dupliquer`), sans la
remplacer : la duplication recopie UNE opération un mois plus loin, en
partant de sa date ; un modèle calcule chaque échéance depuis son ANCRE, et
ne dérive donc jamais (31/01 → 28/02 → 31/03, pas 28/03).

Charges uniquement, par LISTE BLANCHE : une liste noire laisserait passer
tout gabarit ajouté plus tard sans que personne ait décidé qu'il pouvait
être récurrent. Les loyers en sont exclus : un loyer ne s'enregistre qu'une
fois encaissé, et les quittances lisent les écritures.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime

import echeancier

SOURCE = "recurrent"

PERIODICITES = {"mensuelle": 1, "trimestrielle": 3, "semestrielle": 6,
                "annuelle": 12}
DERNIER_JOUR = 0            # valeur de `jour` : dernier jour du mois

# Gabarits admis. Tous de nature « charge », sur un compte de classe 6
# (vérifié par les tests). Exclus de fait : toute recette, les mouvements de
# bilan (emprunt, dépôt de garantie, attente), les intérêts et frais
# d'emprunt (fonction emprunts), les achats ponctuels et frais variables,
# les gabarits personnalisés.
GABARITS_ADMIS = (
    "charge_copro", "fonds_travaux_alur",
    "assurance", "assurance_gli", "assurance_emprunteur",
    "telecom", "energie", "maintenance",
    "gestion_locative", "honoraires", "cotisations_pro", "frais_bancaires",
    "taxe_fonciere", "cfe", "publicite_annonces",
)

# Aides affichées au choix du gabarit. Aucune date fiscale n'est codée : les
# calendriers changent chaque année.
_AIDE_MENSUALISATION = (
    "Mensualisation : les prélèvements mensuels sont des acomptes. La "
    "régularisation de fin d'année (solde à payer ou trop-perçu remboursé) "
    "se saisit à la main, comme une opération ordinaire. Le montant des "
    "prélèvements change chaque année : mettez le modèle à jour à "
    "réception du nouvel avis.")
AIDES = {"taxe_fonciere": _AIDE_MENSUALISATION, "cfe": _AIDE_MENSUALISATION}

LONGUEUR_TEXTE = 120


def assurer_schema(conn: sqlite3.Connection) -> None:
    """Tables des modèles et du moteur (palier de migration 10). Sans commit."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS modele_recurrent ("
        " id          INTEGER PRIMARY KEY,"
        " type        TEXT    NOT NULL,"
        " bien_id     INTEGER NOT NULL REFERENCES bien(id),"
        " montant     REAL    NOT NULL CHECK (montant > 0),"
        " libelle     TEXT,"
        " tiers       TEXT,"
        " periodicite TEXT    NOT NULL CHECK (periodicite IN"
        "             ('mensuelle','trimestrielle','semestrielle','annuelle')),"
        " jour        INTEGER NOT NULL CHECK (jour BETWEEN 0 AND 31),"
        " date_debut  TEXT    NOT NULL,"
        " date_fin    TEXT,"
        " actif       INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0,1)),"
        " cree_le     TEXT    NOT NULL,"
        " CHECK (date_fin IS NULL OR date_fin >= date_debut))")
    echeancier.assurer_schema(conn)


# ── Validation ───────────────────────────────────────────────────────────

def _date(valeur, quoi: str) -> date:
    if isinstance(valeur, date):
        return valeur
    try:
        if len(valeur) != 10:
            raise ValueError
        return date.fromisoformat(valeur)
    except (TypeError, ValueError):
        raise ValueError(f"{quoi} invalide : « {valeur} » (format attendu "
                         "AAAA-MM-JJ).") from None


def _texte(valeur, quoi: str) -> str | None:
    if valeur is None:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in valeur):
        raise ValueError(f"{quoi} : tabulation et saut de ligne refusés.")
    valeur = valeur.strip()
    if len(valeur) > LONGUEUR_TEXTE:
        raise ValueError(f"{quoi} trop long : {LONGUEUR_TEXTE} caractères "
                         "au plus.")
    return valeur or None


def verifier_gabarit(type_: str) -> None:
    if type_ not in GABARITS_ADMIS:
        import gabarits
        g = gabarits.tous().get(type_)
        nom = f"« {g['libelle']} »" if g else f"« {type_} »"
        raise ValueError(
            f"Le gabarit {nom} ne peut pas être récurrent. Seules les charges "
            "qui reviennent à l'identique le peuvent (assurance, abonnement, "
            "copropriété…). Un loyer ne s'enregistre qu'une fois encaissé ; "
            "un achat, une immobilisation ou un remboursement d'emprunt se "
            "saisissent à l'unité.")


def jour_normalise(valeur) -> int:
    if isinstance(valeur, str) and valeur.strip().lower() in (
            "dernier", "fin", "dernier jour"):
        return DERNIER_JOUR
    try:
        j = int(valeur)
    except (TypeError, ValueError):
        raise ValueError(f"Jour d'échéance invalide : « {valeur} » (1 à 31, "
                         "ou « dernier jour du mois »).") from None
    if not 0 <= j <= 31:
        raise ValueError(f"Jour d'échéance invalide : {j} (1 à 31, ou "
                         "« dernier jour du mois »).")
    return j


def _valider(conn, *, type, bien_id, montant, periodicite, jour, date_debut,
             date_fin=None, libelle=None, tiers=None) -> dict:
    verifier_gabarit(type)
    try:
        bien_id = int(bien_id)
    except (TypeError, ValueError):
        raise ValueError("Bien invalide.") from None
    if not conn.execute("SELECT 1 FROM bien WHERE id=?", (bien_id,)).fetchone():
        raise ValueError(f"Aucun bien n° {bien_id} dans ce dossier.")
    try:
        montant = float(montant)
    except (TypeError, ValueError):
        raise ValueError(f"Montant invalide : « {montant} ».") from None
    if not math.isfinite(montant) or round(montant, 2) <= 0:
        raise ValueError("Le montant doit être strictement positif.")
    if periodicite not in PERIODICITES:
        raise ValueError(f"Périodicité inconnue : « {periodicite} » "
                         "(mensuelle, trimestrielle, semestrielle, annuelle).")
    debut = _date(date_debut, "Date de début")
    fin = _date(date_fin, "Date de fin") if date_fin else None
    if fin is not None and fin < debut:
        raise ValueError("La date de fin précède la date de début.")
    return {"type": type, "bien_id": bien_id, "montant": round(montant, 2),
            "periodicite": periodicite, "jour": jour_normalise(jour),
            "date_debut": debut.isoformat(),
            "date_fin": fin.isoformat() if fin else None,
            "libelle": _texte(libelle, "Libellé"),
            "tiers": _texte(tiers, "Tiers")}


# ── Modèles ──────────────────────────────────────────────────────────────

def creer(conn: sqlite3.Connection, **champs) -> int:
    assurer_schema(conn)
    v = _valider(conn, **champs)
    cur = conn.execute(
        "INSERT INTO modele_recurrent (type, bien_id, montant, libelle, tiers, "
        "periodicite, jour, date_debut, date_fin, actif, cree_le) "
        "VALUES (?,?,?,?,?,?,?,?,?,1,?)",
        (v["type"], v["bien_id"], v["montant"], v["libelle"], v["tiers"],
         v["periodicite"], v["jour"], v["date_debut"], v["date_fin"],
         datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    return cur.lastrowid


def modele(conn: sqlite3.Connection, modele_id: int) -> dict:
    assurer_schema(conn)
    cur = conn.execute("SELECT * FROM modele_recurrent WHERE id=?", (modele_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"Aucun modèle récurrent n° {modele_id}.")
    return dict(zip([c[0] for c in cur.description], row))


def modifier(conn: sqlite3.Connection, modele_id: int, **champs) -> None:
    """Remplace les champs donnés. Les opérations DÉJÀ générées ne sont
    jamais touchées : elles sont indépendantes du modèle."""
    actuel = modele(conn, modele_id)
    base = {k: actuel[k] for k in ("type", "bien_id", "montant", "periodicite",
                                   "jour", "date_debut", "date_fin",
                                   "libelle", "tiers")}
    base.update(champs)
    v = _valider(conn, **base)
    conn.execute(
        "UPDATE modele_recurrent SET type=?, bien_id=?, montant=?, libelle=?, "
        "tiers=?, periodicite=?, jour=?, date_debut=?, date_fin=? WHERE id=?",
        (v["type"], v["bien_id"], v["montant"], v["libelle"], v["tiers"],
         v["periodicite"], v["jour"], v["date_debut"], v["date_fin"],
         modele_id))
    conn.commit()


def activer(conn: sqlite3.Connection, modele_id: int, actif: bool) -> None:
    modele(conn, modele_id)
    conn.execute("UPDATE modele_recurrent SET actif=? WHERE id=?",
                 (1 if actif else 0, modele_id))
    conn.commit()


def supprimer(conn: sqlite3.Connection, modele_id: int) -> dict:
    """Supprime le modèle, PAS ses opérations : elles sont des paiements
    enregistrés, pas des dépendances du modèle."""
    m = modele(conn, modele_id)
    n = conn.execute("SELECT COUNT(*) FROM echeance_generee WHERE source=? "
                     "AND source_id=? AND etat='generee'",
                     (SOURCE, modele_id)).fetchone()[0]
    conn.execute("DELETE FROM modele_recurrent WHERE id=?", (modele_id,))
    conn.commit()
    return {"modele": m, "operations_conservees": n}


def depuis_operation(conn: sqlite3.Connection, operation_id: int, *,
                     periodicite: str = "mensuelle") -> int:
    """Crée un modèle à partir d'une opération : gabarit, bien, montant,
    libellé et tiers repris ; jour et début tirés de sa date."""
    import operations
    operations.assurer_colonne_annulee(conn)
    cur = conn.execute(
        "SELECT type, bien_id, montant, libelle, tiers, date_operation, "
        "COALESCE(annulee,0), source FROM operation WHERE id=?",
        (operation_id,))
    op = cur.fetchone()
    if op is None:
        raise ValueError(f"Opération {operation_id} introuvable.")
    type_, bien_id, montant, libelle, tiers, jour, annulee, source = op
    if annulee:
        raise ValueError("Cette opération est annulée : elle ne peut pas "
                         "servir de modèle.")
    if source == "emprunt":
        # L'assurance d'une échéance d'emprunt est déjà générée avec
        # l'échéance : un modèle récurrent la compterait deux fois.
        raise ValueError("Cette opération vient d'une échéance d'emprunt : "
                         "elle est générée depuis l'onglet Emprunts, pas "
                         "par un modèle récurrent.")
    verifier_gabarit(type_)
    import gabarits
    if libelle == gabarits.GABARITS[type_]["libelle"]:
        libelle = None                    # libellé par défaut : non recopié
    d = date.fromisoformat(jour)
    return creer(conn, type=type_, bien_id=bien_id, montant=montant,
                 libelle=libelle, tiers=tiers or None, periodicite=periodicite,
                 jour=d.day, date_debut=d.isoformat())


def lister(conn: sqlite3.Connection) -> list[dict]:
    assurer_schema(conn)
    import gabarits
    # Catalogue du CODE, sans lecture en base : les gabarits admis y sont
    # tous (les personnalisés sont exclus), et la page Saisie ne doit lire
    # le catalogue qu'une fois (constat T-09).
    libelles = {k: v["libelle"] for k, v in gabarits.GABARITS.items()}
    biens = dict(conn.execute("SELECT id, libelle FROM bien"))
    cur = conn.execute("SELECT * FROM modele_recurrent ORDER BY actif DESC, id")
    noms = [c[0] for c in cur.description]
    out = []
    for row in cur.fetchall():
        m = dict(zip(noms, row))
        m["gabarit_libelle"] = libelles.get(m["type"], m["type"])
        m["bien_libelle"] = biens.get(m["bien_id"], f"bien n° {m['bien_id']}")
        m["jour_libelle"] = ("dernier jour du mois" if m["jour"] == DERNIER_JOUR
                             else f"le {m['jour']}")
        out.append(m)
    return out


# ── Calendrier ───────────────────────────────────────────────────────────

def date_du_rang(m: dict, rang: int) -> date:
    """Date de la `rang`-ième échéance, calculée depuis l'ANCRE (mois de
    début) — jamais depuis l'échéance précédente, pour ne pas dériver."""
    return echeancier.date_ancree(date.fromisoformat(m["date_debut"]),
                                  PERIODICITES[m["periodicite"]], rang,
                                  jour=m["jour"])


def grille(m: dict, du: date, au: date) -> list[tuple[date, str | None]]:
    """Échéances de la grille du modèle entre `du` et `au` (inclus), avec le
    motif de mise à l'écart lié au modèle lui-même (None si aucun)."""
    debut = date.fromisoformat(m["date_debut"])
    fin = date.fromisoformat(m["date_fin"]) if m["date_fin"] else None
    out, rang = [], 0
    while True:
        d = date_du_rang(m, rang)
        rang += 1
        if d > au:
            return out
        if d < du:
            continue
        if d < debut:
            motif = (f"avant le début du modèle "
                     f"({debut.strftime('%d/%m/%Y')})")
        elif fin is not None and d > fin:
            motif = f"après la fin du modèle ({fin.strftime('%d/%m/%Y')})"
        elif not m["actif"]:
            motif = "modèle suspendu"
        else:
            motif = None
        out.append((d, motif))


def echeances(conn: sqlite3.Connection, du: date, au: date,
              modele_ids: set[int] | None = None) -> list[echeancier.Echeance]:
    """Échéances de tous les modèles (suspendus compris, pour dire pourquoi
    ils ne génèrent rien) sur la période."""
    out = []
    for m in lister(conn):
        if modele_ids is not None and m["id"] not in modele_ids:
            continue
        for d, motif in grille(m, du, au):
            out.append(echeancier.Echeance(
                source=SOURCE, source_id=m["id"], date=d, bien_id=m["bien_id"],
                libelle=m["libelle"] or m["gabarit_libelle"],
                motif_source=motif,
                operations=[{"type": m["type"], "montant": m["montant"],
                             "libelle": m["libelle"], "tiers": m["tiers"],
                             "periode": f"{d.year:04d}-{d.month:02d}",
                             "piece_ref": f"Relevé bancaire {d.month:02d}"}]))
    return out


def periode_par_defaut(conn, annee: int) -> tuple[date, date]:
    row = conn.execute("SELECT date_debut, date_fin FROM exercice WHERE annee=?",
                       (annee,)).fetchone()
    if row:
        return date.fromisoformat(row[0]), date.fromisoformat(row[1])
    return date(annee, 1, 1), date(annee, 12, 31)


def apercu(conn, du: date, au: date, *, aujourd_hui: date | None = None):
    return echeancier.apercu(conn, echeances(conn, du, au),
                             aujourd_hui=aujourd_hui)


def generer(conn, du: date, au: date, retenues: set[str], *,
            ecarter: set[str] = frozenset(),
            aujourd_hui: date | None = None) -> dict:
    return echeancier.generer(conn, echeances(conn, du, au), retenues,
                              ecarter=ecarter, aujourd_hui=aujourd_hui)


def resume(conn, annee: int) -> dict:
    """Pour la carte de la page Saisie."""
    du, au = periode_par_defaut(conn, annee)
    lignes = apercu(conn, du, au)
    return {"actifs": sum(1 for m in lister(conn) if m["actif"]),
            "a_generer": sum(1 for x in lignes
                             if x.statut == echeancier.A_GENERER)}


def message_generation(r: dict) -> str:
    msg = f"{r['nb_operations']} opération(s) générée(s)"
    if r["ecartees"]:
        msg += f", {len(r['ecartees'])} échéance(s) écartée(s)"
    msg += "."
    if r["non_generees"]:
        msg += (f" {len(r['non_generees'])} échéance(s) retenue(s) n'étaient "
                "plus à générer (déjà générées entre-temps, ou devenues "
                "inéligibles) : elles n'ont pas été créées.")
    return msg
