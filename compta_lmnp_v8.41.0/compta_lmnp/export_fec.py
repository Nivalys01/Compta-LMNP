# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
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
JOIN journal  j ON j.code = e.journal_code
JOIN compte   c ON c.numero = l.compte_num
WHERE e.exercice_annee = ?
ORDER BY e.ecriture_num, l.id
"""


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
    """Écrit le FEC de l'exercice et renvoie le chemin produit."""
    lignes = lignes_fec(conn, annee)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(COLONNES) + "\r\n")
        for lg in lignes:
            f.write("\t".join(lg) + "\r\n")
    return chemin
