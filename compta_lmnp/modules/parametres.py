# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

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

import datetime
import math

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


# Domaine de validité de chaque règle livrée : (minimum, maximum, entier).
# Une règle fiscale est versionnable, pas arbitraire. Sans domaine, une
# durée de report saisie à ZÉRO faisait expirer un déficit l'année même de
# sa naissance — 1 200 € purgés par le moteur, et un bénéfice de 1 200 €
# laissé sans son imputation. Un seuil négatif, lui, déclenche une alerte
# sur toute dépense ; un seuil démesuré n'en déclenche plus aucune.
DOMAINES: dict[str, tuple] = {
    "seuil_immobilisation": (1.0, 100_000.0, False),
    "duree_report_deficit_lmnp": (1.0, 30.0, True),
    "seuil_lmp_recettes": (1.0, 10_000_000.0, False),
    "seuil_micro_bic_meuble": (1.0, 10_000_000.0, False),
    "retraitement_alur_auto": (0.0, 1.0, True),
}


# Marque apposée au commentaire d'une règle RECRÉÉE après coup, c'est-à-dire
# réapparue alors que d'autres règles existaient déjà — signature d'une
# configuration perdue, et non d'une première initialisation.
MARQUE_RETABLIE = " [rétablie à sa valeur livrée]"
# Clé de `meta` posée au premier ensemencement des règles.
MARQUE_SEMEES = "regles_fiscales_semees_le"


def regles_retablies(conn: sqlite3.Connection) -> list[str]:
    """Clés des règles recréées à leur valeur livrée après une disparition.

    Leur valeur d'origine n'est pas récupérable : la table d'historique ne
    conserve que ce qui s'y trouve. Le seul service honnête est de DIRE
    que la valeur affichée n'est peut-être pas celle qui s'appliquait.
    """
    assurer(conn)
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT cle FROM regle_fiscale WHERE commentaire LIKE ?",
        ("%" + MARQUE_RETABLIE + "%",))]


def verifier_domaine(cle: str, valeur_numerique: float) -> None:
    """Lève ValueError si la valeur sort du domaine admis pour cette règle."""
    if not math.isfinite(valeur_numerique):
        raise ValueError(
            f"Valeur de règle invalide pour « {cle} » : un seuil doit être "
            "un nombre fini. Une valeur infinie rendrait définitivement "
            "muets les contrôles qui s'y comparent.")
    borne = DOMAINES.get(cle)
    if borne is None:
        return                     # règle personnalisée : domaine inconnu
    mini, maxi, entier = borne
    libelle = LIBELLES.get(cle, cle)
    if entier and abs(valeur_numerique - round(valeur_numerique)) > 1e-9:
        raise ValueError(f"« {libelle} » attend un nombre entier : "
                         f"{valeur_numerique} n'en est pas un.")
    if not (mini <= valeur_numerique <= maxi):
        raise ValueError(
            f"« {libelle} » : {valeur_numerique:g} est hors du domaine admis "
            f"({mini:g} à {maxi:g}). Une valeur hors de ces bornes ne "
            "traduit aucune disposition applicable — elle ne ferait que "
            "neutraliser les calculs qui s'y réfèrent.")


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
    # Une table VIDE ne dit pas si c'est la première ouverture du dossier
    # ou la disparition de sa configuration : les deux se présentent
    # exactement pareil. On pose donc une marque durable au premier
    # ensemencement, et c'est son absence — et non celle des règles — qui
    # signe une première fois.
    conn.execute("CREATE TABLE IF NOT EXISTS meta ("
                 "cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")
    deja_seme = conn.execute("SELECT 1 FROM meta WHERE cle=?",
                             (MARQUE_SEMEES,)).fetchone() is not None
    premiere_fois = not deja_seme
    for cle, valeur, debut, ref, com, _lib in REGLES_DEFAUT:
        n = conn.execute("SELECT COUNT(*) FROM regle_fiscale WHERE cle=?",
                         (cle,)).fetchone()[0]
        if n == 0:
            # Le commentaire porte la TRACE de cette réinsertion. Une règle
            # recréée en silence est indiscernable d'une règle jamais
            # touchée : un seuil abaissé à 300 €, puis perdu, revenait à
            # 500 € et l'avertissement disparaissait avec lui, sans que
            # rien ne distingue cette perte d'une première initialisation.
            # `regles_retablies()` permet de la signaler.
            conn.execute(
                "INSERT INTO regle_fiscale (cle, valeur, date_debut, reference, "
                "commentaire) VALUES (?,?,?,?,?)",
                (cle, valeur, debut, ref,
                 com if premiere_fois else com + MARQUE_RETABLIE))
    conn.execute("INSERT INTO meta (cle, valeur) VALUES (?, ?) "
                 "ON CONFLICT(cle) DO NOTHING",
                 (MARQUE_SEMEES, datetime.date.today().isoformat()))
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
    # …et la nouvelle version reçoit sa propre fin lorsqu'une version
    # POSTÉRIEURE existe déjà. Seule la clôture de la version précédente
    # était faite : saisir une règle rétroactive laissait donc deux
    # périodes ouvertes en même temps, et l'historique se contredisait.
    # Le tri par date décroissante sauvait le calcul, mais il ne peut pas
    # servir de justification devant un vérificateur — et il suffisait de
    # clore la version la plus récente pour voir l'ancienne ressurgir.
    suivante = conn.execute(
        "SELECT MIN(date_debut) FROM regle_fiscale WHERE cle=? AND "
        "date_debut>?", (cle, date_debut)).fetchone()[0]
    fin = _veille(suivante) if suivante else None
    # Une règle fiscale est un NOMBRE FINI. `float()` accepte « inf » et
    # « 1e309 » : enregistrer un seuil infini rendait muets, pour toujours
    # et sans un mot, les contrôles qui s'y comparent — aucune dépense ne
    # dépasse l'infini. Un garde-fou qu'on peut désactiver par une saisie
    # est pire qu'un garde-fou absent : on croit encore l'avoir.
    try:
        valeur_numerique = float(nouvelle_valeur)
    except (TypeError, ValueError):
        raise ValueError(f"Valeur de règle invalide pour « {cle} » : "
                         f"{nouvelle_valeur!r} n'est pas un nombre.") from None
    verifier_domaine(cle, valeur_numerique)
    conn.execute(
        "INSERT INTO regle_fiscale (cle, valeur, date_debut, date_fin, "
        "reference, commentaire) VALUES (?,?,?,?,?,?)",
        (cle, valeur_numerique, date_debut, fin, reference, commentaire))
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
