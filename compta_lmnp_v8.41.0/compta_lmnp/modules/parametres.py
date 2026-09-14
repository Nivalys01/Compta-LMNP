# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Règles fiscales VERSIONNÉES — le point d'entrée des dispositions légales.

Principe : aucune valeur réglementaire (seuil, durée, taux, activation d'un
retraitement) n'est figée dans le code. Chaque règle vit dans la table
`regle_fiscale` avec une période de validité :

    cle | valeur | date_debut | date_fin (NULL = en vigueur) | reference | commentaire

Quand une loi de finances change un seuil, on n'édite PAS le code : on
enregistre une nouvelle valeur avec sa date d'effet (menu « Réglementation »
ou `definir()`). Le moteur sélectionne automatiquement la valeur en vigueur
pour l'exercice traité — les exercices passés restent calculés avec les
règles de leur époque (millésime), condition indispensable pour rejouer ou
justifier un exercice ancien.

Règles livrées (valeurs 2026, références légales en commentaire) :
    seuil_immobilisation        500 €   BOI-BIC-CHG-20-30-10 (tolérance)
    duree_report_deficit_lmnp   10 ans  art. 156, I-1° ter CGI
    seuil_lmp_recettes          23 000  art. 155, IV CGI
    seuil_micro_bic_meuble      77 700  art. 50-0 CGI
    retraitement_alur_auto      1       fonds travaux non déductible
                                        (BOI-BIC-CHG-40-20 ; provision, pas charge)
"""
from __future__ import annotations

import sqlite3

# (cle, valeur, date_debut, reference, commentaire, libelle humain)
REGLES_DEFAUT = [
    ("seuil_immobilisation", 500.0, "2000-01-01",
     "BOI-BIC-CHG-20-30-10",
     "Tolérance administrative : matériel/mobilier < 500 € HT passé en charge.",
     "Seuil d'immobilisation (€)"),
    ("duree_report_deficit_lmnp", 10, "2000-01-01",
     "Art. 156, I-1° ter CGI",
     "Déficit LMNP imputable sur revenus de même nature pendant N années.",
     "Report des déficits LMNP (années)"),
    ("seuil_lmp_recettes", 23000.0, "2000-01-01",
     "Art. 155, IV CGI",
     "Recettes annuelles au-delà desquelles le statut LMP peut s'appliquer.",
     "Seuil LMP — recettes (€)"),
    ("seuil_micro_bic_meuble", 77700.0, "2023-01-01",
     "Art. 50-0 CGI",
     "Plafond micro-BIC location meublée (cas général).",
     "Seuil micro-BIC meublé (€)"),
    ("retraitement_alur_auto", 1, "2000-01-01",
     "BOI-BIC-CHG-40-20",
     "Réintégration fiscale automatique du fonds travaux ALUR à la clôture "
     "(1 = active, 0 = inactive).",
     "Réintégration ALUR automatique (0/1)"),
]

LIBELLES = {cle: lib for cle, *_rest, lib in REGLES_DEFAUT}

# Où chaque règle agit RÉELLEMENT. Une règle versionnée n'a de valeur que si
# l'utilisateur sait ce qu'elle change : un seuil qui ne sert qu'à émettre un
# avertissement ne doit pas être confondu avec une règle qui modifie le
# résultat fiscal. Affiché en clair dans le menu « Réglementation ».
IMPACTS = {
    "seuil_immobilisation": (
        "Contrôle de saisie",
        "Avertissement avant clôture si une dépense au-delà du seuil est "
        "passée en charge (elle relèverait plutôt d'une immobilisation). "
        "N'change JAMAIS le compte utilisé ni le résultat : c'est à vous de "
        "requalifier la dépense si l'avertissement est justifié."),
    "duree_report_deficit_lmnp": (
        "Clôture fiscale",
        "Durée de vie des déficits LMNP : au-delà, un déficit non imputé "
        "expire et disparaît des reports."),
    "seuil_lmp_recettes": (
        "Pense-bête",
        "Au-delà de ce montant de recettes, un rappel signale le passage "
        "possible au statut LMP. Aucun effet sur les calculs."),
    "seuil_micro_bic_meuble": (
        "Information",
        "Plafond du régime micro-BIC, rappelé à titre indicatif : ce "
        "logiciel tient une comptabilité au réel."),
    "retraitement_alur_auto": (
        "Clôture fiscale",
        "À 1 (valeur livrée) : le fonds travaux ALUR saisi dans l'exercice "
        "est réintégré automatiquement au résultat fiscal, sans saisie "
        "manuelle. À 0 : la réintégration devient votre responsabilité."),
}


def impact(cle: str) -> tuple[str, str]:
    """(module concerné, effet concret) — « Non documenté » si règle ajoutée
    par l'utilisateur."""
    return IMPACTS.get(cle, ("Non documenté",
                             "Règle personnalisée : son effet dépend de "
                             "l'usage qui en est fait."))


def assurer(conn: sqlite3.Connection) -> None:
    """Crée la table si besoin et insère les règles par défaut manquantes."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS regle_fiscale ("
        "  id          INTEGER PRIMARY KEY,"
        "  cle         TEXT NOT NULL,"
        "  valeur      REAL NOT NULL,"
        "  date_debut  TEXT NOT NULL,"           # AAAA-MM-JJ (date d'effet)
        "  date_fin    TEXT,"                    # NULL = toujours en vigueur
        "  reference   TEXT NOT NULL DEFAULT ''," # texte légal (CGI, BOFiP, LF)
        "  commentaire TEXT NOT NULL DEFAULT '')")
    for cle, valeur, debut, ref, com, _lib in REGLES_DEFAUT:
        n = conn.execute("SELECT COUNT(*) FROM regle_fiscale WHERE cle=?",
                         (cle,)).fetchone()[0]
        if n == 0:
            conn.execute(
                "INSERT INTO regle_fiscale (cle, valeur, date_debut, reference, "
                "commentaire) VALUES (?,?,?,?,?)", (cle, valeur, debut, ref, com))
    # Même précaution que `gabarits.assurer_table` : cette fonction sème la
    # table au premier accès, donc sur un chemin de LECTURE — `valeur()`
    # l'appelle. Committer inconditionnellement terminerait la transaction
    # d'un appelant travaillant en commit=False, sans qu'il le sache
    # (constat D2-08).
    if not conn.in_transaction:
        conn.commit()


def valeur(conn: sqlite3.Connection, cle: str, annee: int,
           defaut: float | None = None) -> float:
    """
    Valeur de la règle EN VIGUEUR pour l'exercice `annee` : la version dont la
    date d'effet est la plus récente parmi celles ≤ 31/12/annee et non closes
    avant le 01/01/annee. Les exercices passés gardent ainsi leurs règles.
    """
    assurer(conn)
    row = conn.execute(
        "SELECT valeur FROM regle_fiscale WHERE cle=? AND date_debut<=? "
        "AND (date_fin IS NULL OR date_fin>=?) "
        "ORDER BY date_debut DESC LIMIT 1",
        (cle, f"{annee}-12-31", f"{annee}-01-01")).fetchone()
    if row is not None:
        return row[0]
    if defaut is not None:
        return defaut
    raise ValueError(f"Règle fiscale inconnue pour {annee} : {cle!r}")


def definir(conn: sqlite3.Connection, cle: str, nouvelle_valeur: float,
            date_debut: str, reference: str = "", commentaire: str = "") -> None:
    """
    Enregistre une NOUVELLE version d'une règle (disposition légale future) :
    clôt la version précédente à la veille de la date d'effet, puis insère la
    nouvelle. L'historique complet est conservé.
    """
    assurer(conn)
    if len(date_debut) != 10:
        raise ValueError("date_debut attendue au format AAAA-MM-JJ.")
    # Clore la version couvrant la nouvelle date d'effet.
    an, mois, jour = date_debut.split("-")
    veille = _veille(date_debut)
    # Une version portant EXACTEMENT la même date d'effet remplace la
    # précédente au lieu de coexister avec elle : deux lignes à date égale
    # rendaient le « ORDER BY date_debut DESC LIMIT 1 » arbitraire — le
    # menu affichait la nouvelle règle pendant que le moteur appliquait
    # l'ancienne.
    conn.execute("DELETE FROM regle_fiscale WHERE cle=? AND date_debut=?",
                 (cle, date_debut))
    conn.execute(
        "UPDATE regle_fiscale SET date_fin=? WHERE cle=? AND date_debut<? "
        "AND (date_fin IS NULL OR date_fin>=?)",
        (veille, cle, date_debut, date_debut))
    conn.execute(
        "INSERT INTO regle_fiscale (cle, valeur, date_debut, reference, commentaire) "
        "VALUES (?,?,?,?,?)",
        (cle, float(nouvelle_valeur), date_debut, reference, commentaire))
    conn.commit()


def historique(conn: sqlite3.Connection) -> list[dict]:
    """Toutes les versions de toutes les règles, pour le menu Réglementation."""
    assurer(conn)
    rows = conn.execute(
        "SELECT cle, valeur, date_debut, date_fin, reference, commentaire "
        "FROM regle_fiscale ORDER BY cle, date_debut").fetchall()
    return [{"cle": c, "libelle": LIBELLES.get(c, c), "valeur": v,
             "date_debut": d, "date_fin": f, "reference": r, "commentaire": com}
            for c, v, d, f, r, com in rows]


def _veille(date_iso: str) -> str:
    from datetime import date, timedelta
    a, m, j = (int(x) for x in date_iso.split("-"))
    return (date(a, m, j) - timedelta(days=1)).isoformat()
