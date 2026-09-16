# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
# sans autorisation écrite de l'auteur.

"""
Jalon J3 — Sérialiseur FEC (A47 A-1).

Exporte les écritures d'un exercice au format réglementaire :
séparateur TABULATION, décimale VIRGULE, fins de ligne CRLF, dates AAAAMMJJ,
18 colonnes dans l'ordre. Montants au format des logiciels du marché (zéros décimaux superflus
supprimés ; champ vide quand le montant est nul).
"""
from __future__ import annotations
import sqlite3

COLONNES = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum",
    "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef", "PieceDate",
    "EcritureLib", "Debit", "Credit", "EcritureLet", "DateLet", "ValidDate",
    "Montantdevise", "Idevise",
]


def serialiser_montant(x) -> str:
    """0 -> '' ; sinon décimale virgule sans zéros superflus (8599.5 -> '8599,5')."""
    v = round(float(x or 0), 2)
    if abs(v) < 0.005:
        return ""
    s = f"{v:.2f}".replace(".", ",")
    return s.rstrip("0").rstrip(",")


# Requête directe (mêmes colonnes et même ordre que la vue v_fec) : la vue
# n'expose pas l'exercice, or la numérotation redémarre à 1 chaque année —
# filtrer v_fec par EcritureNum mélangeait donc les exercices dès qu'il y en
# avait plusieurs en base. Ici le filtre porte explicitement sur
# e.exercice_annee ; v_fec est conservée (consultation, tests J0/J1).
_SQL_FEC = """
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
LEFT JOIN journal  j ON j.code = e.journal_code
LEFT JOIN compte   c ON c.numero = l.compte_num
WHERE e.exercice_annee = ?
ORDER BY e.ecriture_date, e.ecriture_num, l.id
"""
# Deux choix, dans cette requête, tiennent à des défauts constatés :
#
# LEFT JOIN sur le journal et le compte. Les jointures internes faisaient
# DISPARAÎTRE du fichier toute ligne dont le compte ou le journal manquait au
# plan — l'export se terminait normalement, le validateur trouvait le fichier
# conforme, et 800 € présents en base n'étaient nulle part. Un export ne doit
# pas pouvoir taire ce qu'il ne sait pas restituer : la ligne sort désormais
# avec un libellé vide, que le validateur signale, et `exporter()` refuse le
# fichier (voir `_verifier_exhaustivite`).
#
# ORDER BY sur la DATE avant le numéro. La numérotation suit l'ordre de
# SAISIE : un loyer de mars saisi avant celui de janvier sortait en tête du
# fichier, dont la chronologie — dates d'écriture comme dates de validation —
# reculait alors d'un bloc à l'autre. Rien ne l'interdit formellement, mais
# c'est le premier motif de question d'un vérificateur, et l'ordre
# chronologique ne coûte rien.


def _verifier_exhaustivite(conn: sqlite3.Connection, annee: int,
                           lignes: list[list[str]]) -> None:
    """Refuse d'écrire un FEC qui ne rendrait pas ce que la base contient.

    Un export silencieusement incomplet est plus dangereux qu'un export en
    échec : il produit un fichier d'apparence normale, que le validateur
    approuve, et dont personne ne peut deviner qu'il manque des écritures.
    """
    attendu = conn.execute(
        "SELECT COUNT(*) FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.exercice_annee = ?", (annee,)).fetchone()[0]
    if len(lignes) != attendu:
        raise ValueError(
            f"Export interrompu : l'exercice {annee} compte {attendu} "
            f"ligne(s) en base et {len(lignes)} seraient écrites. Le fichier "
            "serait incomplet — il n'est pas produit.")
    orphelines = conn.execute(
        "SELECT DISTINCT l.compte_num FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id "
        "LEFT JOIN compte c ON c.numero = l.compte_num "
        "WHERE e.exercice_annee = ? AND c.numero IS NULL", (annee,)).fetchall()
    if orphelines:
        raise ValueError(
            "Export interrompu : des écritures utilisent des comptes absents "
            f"du plan — {', '.join(str(o[0]) for o in orphelines)}. Leur "
            "libellé est obligatoire au FEC. Rétablissez ces comptes avant "
            "d'exporter.")
    sans_journal = conn.execute(
        "SELECT DISTINCT e.journal_code FROM ecriture e "
        "LEFT JOIN journal j ON j.code = e.journal_code "
        "WHERE e.exercice_annee = ? AND j.code IS NULL", (annee,)).fetchall()
    if sans_journal:
        raise ValueError(
            "Export interrompu : des écritures portent des journaux absents "
            f"du référentiel — {', '.join(str(o[0]) for o in sans_journal)}.")
    vides = conn.execute(
        "SELECT e.ecriture_num FROM ecriture e "
        "LEFT JOIN ligne l ON l.ecriture_id = e.id "
        "WHERE e.exercice_annee = ? AND l.id IS NULL "
        "ORDER BY e.ecriture_num", (annee,)).fetchall()
    if vides:
        raise ValueError(
            "Export interrompu : écriture(s) sans aucune ligne — "
            f"n° {', '.join(str(v[0]) for v in vides)}. Un en-tête sans ligne "
            "est un trou dans la numérotation du FEC.")


def lignes_fec(conn: sqlite3.Connection, annee: int) -> list[list[str]]:
    """Renvoie les lignes (listes de 18 chaînes) pour un exercice donné."""
    cur = conn.execute(_SQL_FEC, (annee,))
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    idx = {c: i for i, c in enumerate(cols)}
    out: list[list[str]] = []
    for r in rows:
        ligne = []
        for c in COLONNES:
            val = r[idx[c]]
            if c in ("Debit", "Credit"):
                ligne.append(serialiser_montant(val))
            else:
                ligne.append("" if val is None else str(val))
        out.append(ligne)
    return out


def exporter(conn: sqlite3.Connection, annee: int, chemin: str) -> str:
    """Écrit le FEC de l'exercice et renvoie le chemin produit.

    Lève ValueError plutôt que d'écrire un fichier qui ne restituerait pas
    l'intégralité des écritures de l'exercice."""
    lignes = lignes_fec(conn, annee)
    _verifier_exhaustivite(conn, annee, lignes)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(COLONNES) + "\r\n")
        for lg in lignes:
            f.write("\t".join(lg) + "\r\n")
    return chemin
