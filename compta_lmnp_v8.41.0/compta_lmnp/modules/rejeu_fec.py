# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Rejeu d'un FEC complet dans un exercice — reprise d'historique.

Permet d'importer tel quel un exercice entier depuis son FEC (par exemple
produit par un autre logiciel ou un prestataire comme le fait un cabinet) : chaque
écriture du fichier est réinsérée via le guichet unique, à numéro identique.
C'est le socle du « test en or » (reproduction des liasses réelles) et la
brique d'une future migration client depuis un autre outil.

Particularités gérées :
- journaux et comptes absents du plan : créés à la volée depuis le FEC ;
- montants négatifs (présents dans les à-nouveaux réels) : normalisés par
  équivalence comptable stricte (débit de -X ⇔ crédit de +X) car la base
  impose débit ≥ 0 et crédit ≥ 0 — la balance reste identique au centime ;
- l'équilibre et la conformité restent contrôlés par le guichet unique.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict

import fec_io

import ecritures


def rejouer(conn: sqlite3.Connection, fec_path: str, annee: int) -> dict:
    """Insère toutes les écritures du FEC dans l'exercice `annee` (déjà
    ouvert). Retourne {"ecritures": n, "normalisees": n, "comptes_crees": [...]}."""
    lignes = fec_io.lignes_nommees(fec_path)

    for code, lib in sorted({(r["JournalCode"], r["JournalLib"])
                             for r in lignes}):
        conn.execute("INSERT OR IGNORE INTO journal (code, libelle) VALUES (?,?)",
                     (code, lib))
    comptes_crees = []
    for num, lib in sorted({(r["CompteNum"], r["CompteLib"])
                            for r in lignes}):
        if not conn.execute("SELECT 1 FROM compte WHERE numero=?",
                            (num,)).fetchone():
            # La classe se déduit du 1er caractère du numéro. Certains
            # logiciels tolèrent des comptes alphanumériques (« CLIENTS ») :
            # refus EXPLICITE plutôt qu'un plantage brut sur int().
            if not num[:1].isdigit():
                raise ValueError(
                    f"Compte « {num} » non numérique dans le FEC : le plan "
                    "comptable de ce logiciel suit le PCG (le premier "
                    "chiffre donne la classe). Renumérotez ce compte dans "
                    "le fichier source avant l'import.")
            # `type` est NOT NULL et contraint à une liste fermée :
            # l'omettre faisait échouer toute reprise d'un FEC contenant un
            # compte absent du plan livré — c'est-à-dire presque tous, un
            # cabinet ayant ses propres comptes (401, 512, 615…).
            conn.execute("INSERT INTO compte (numero, libelle, type, classe) "
                         "VALUES (?,?,?,?)",
                         (num, lib, fec_io.type_du_compte(num), int(num[0])))
            comptes_crees.append(num)

    # Une écriture est identifiée par (JOURNAL, numéro), pas par le seul
    # numéro. Beaucoup de logiciels de cabinet numérotent PAR JOURNAL —
    # AC 1..n, BQ 1..n — et grouper sur le seul numéro fusionnait alors des
    # écritures sans rapport : une facture d'achat et son règlement
    # bancaire devenaient une écriture unique, portant le journal et la
    # date de la première. Les balances restaient exactes au centime, si
    # bien que rien ne se voyait — mais l'exercice rejoué n'était plus le
    # FEC source, et son ré-export ne concordait plus avec le fichier remis.
    par_ecriture: dict[tuple, list] = defaultdict(list)
    for r in lignes:
        par_ecriture[((r["JournalCode"] or "").strip(),
                      int(r["EcritureNum"]))].append(r)

    # La base impose l'unicité du numéro dans l'exercice, alors que les
    # numéros du FEC source peuvent se répéter d'un journal à l'autre : on
    # renumérote alors en continu, dans l'ordre des dates du fichier.
    ordre = sorted(par_ecriture,
                   key=lambda k: (par_ecriture[k][0]["EcritureDate"], k))
    renumeroter = len(ordre) != len({n for _, n in ordre})

    # Une reprise s'annule ENTIÈREMENT ou n'a pas lieu. Les écritures sont
    # insérées sans commit intermédiaire ; sans ce rollback, une reprise
    # interrompue laissait une transaction ouverte, que le premier
    # `commit()` venu d'ailleurs figeait — l'utilisateur se retrouvait avec
    # un exercice à moitié repris, sans rapport et sans savoir où il en
    # était.
    n_norm = 0
    try:
        for rang, cle in enumerate(ordre, start=1):
            grp = par_ecriture[cle]
            num = rang if renumeroter else cle[1]
            r0 = grp[0]
            d = r0["EcritureDate"]
            lgs = []
            for r in grp:
                deb = fec_io.nombre(r["Debit"])
                cre = fec_io.nombre(r["Credit"])
                if deb < 0:
                    cre, deb = cre - deb, 0.0
                    n_norm += 1
                elif cre < 0:
                    deb, cre = deb - cre, 0.0
                    n_norm += 1
                lgs.append((r["CompteNum"], round(deb, 2), round(cre, 2),
                            r["EcritureLib"]))
            ecritures.inserer(conn, journal=r0["JournalCode"],
                              date=f"{d[:4]}-{d[4:6]}-{d[6:]}", annee=annee,
                              libelle=r0["EcritureLib"] or "reprise",
                              piece_ref=r0["PieceRef"] or "NA",
                              num=num, commit=False, lignes=lgs)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"ecritures": len(par_ecriture), "normalisees": n_norm,
            "comptes_crees": comptes_crees, "renumerotees": renumeroter}
