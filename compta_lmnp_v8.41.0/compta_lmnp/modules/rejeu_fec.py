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

import datetime
import sqlite3
from collections import defaultdict

import fec_io

import ecritures


def _date_iso(valeur: str, ou: str) -> str:
    """AAAAMMJJ du FEC -> AAAA-MM-JJ de la base. Chaîne vide -> vide."""
    valeur = (valeur or "").strip()
    if not valeur:
        return ""
    if len(valeur) != 8 or not valeur.isdigit():
        raise ValueError(f"{ou} : date '{valeur}' illisible "
                         "(huit chiffres AAAAMMJJ attendus).")
    try:
        d = datetime.date(int(valeur[:4]), int(valeur[4:6]), int(valeur[6:]))
    except ValueError:
        raise ValueError(f"{ou} : date '{valeur}' inexistante au "
                         "calendrier.") from None
    return d.isoformat()


def rejouer(conn: sqlite3.Connection, fec_path: str, annee: int) -> dict:
    """Insère toutes les écritures du FEC dans l'exercice `annee` (déjà
    ouvert). Retourne {"ecritures": n, "normalisees": n, "comptes_crees": [...]}."""
    lignes = fec_io.lignes_nommees(fec_path)
    if not lignes:
        raise ValueError(
            "Ce fichier ne contient aucune ligne d'écriture exploitable : "
            "rien n'a été repris. Vérifiez qu'il s'agit bien du FEC de "
            "l'exercice à reprendre.")

    # Le libellé d'un journal DÉJÀ connu du plan n'est pas remplacé par
    # celui du fichier (INSERT OR IGNORE) : c'est un choix — le plan livré
    # est la référence — mais il fait que le ré-export ne rend pas le
    # libellé du FEC source. On ne le subit plus en silence : la divergence
    # est rapportée à l'appelant, qui l'annonce.
    journaux_renommes = []
    for code, lib in sorted({((r["JournalCode"] or "").strip(),
                              (r["JournalLib"] or "").strip())
                             for r in lignes}):
        existant = conn.execute("SELECT libelle FROM journal WHERE code=?",
                                (code,)).fetchone()
        if existant is None:
            conn.execute("INSERT INTO journal (code, libelle) VALUES (?,?)",
                         (code, lib))
        elif lib and existant[0] != lib:
            journaux_renommes.append(f"{code} : « {lib} » → « {existant[0]} »")
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
                      (r["EcritureNum"] or "").strip())].append(r)

    # La base impose l'unicité du numéro dans l'exercice, alors que les
    # numéros du FEC source peuvent se répéter d'un journal à l'autre : on
    # renumérote alors en continu, dans l'ordre des dates du fichier.
    #
    # EcritureNum est ALPHANUMÉRIQUE dans l'arrêté : « BQ0001 » est un
    # numéro légal, et le `int()` qui se trouvait ici faisait échouer toute
    # reprise d'un fichier qui en portait — sur un `invalid literal for
    # int()`, que rien n'expliquait. La colonne `ecriture_num` de la base
    # est un entier : on renumérote donc, comme pour les numéros répétés,
    # au lieu de refuser le fichier. Le retour le dit (`renumerotees`).
    ordre = sorted(par_ecriture,
                   key=lambda k: (par_ecriture[k][0]["EcritureDate"], k))
    numeriques = all(n.isdigit() for _j, n in ordre)
    renumeroter = (not numeriques
                   or len(ordre) != len({n for _, n in ordre}))

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
            num = rang if renumeroter else int(cle[1])
            r0 = grp[0]
            ou = f"écriture {cle[0]}/{cle[1]}"
            # Toutes les lignes d'une écriture portent LA MÊME date : c'est
            # ce qui fait d'elles une écriture. Seule celle de la première
            # ligne était lue, et les autres étaient réécrites avec : deux
            # lignes datées de deux ANNÉES différentes étaient reprises,
            # sans un mot, sous l'année de la première — une écriture d'un
            # autre exercice entrait ainsi dans celui-ci. La garde du
            # guichet ne pouvait pas la voir, puisque la date lui arrivait
            # déjà uniformisée.
            dates = {(r["EcritureDate"] or "").strip() for r in grp}
            if len(dates) > 1:
                raise ValueError(
                    f"Le FEC porte des dates différentes sur les lignes de "
                    f"l'{ou} : {', '.join(sorted(dates))}. Les lignes d'une "
                    "même écriture doivent partager sa date. Corrigez le "
                    "fichier source avant l'import.")
            d = _date_iso(r0["EcritureDate"], ou.capitalize())
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
                # Les champs facultatifs du FEC source sont CONSERVÉS.
                # Ils étaient perdus : identification auxiliaire, lettrage
                # et devise revenaient vides au ré-export, et un fichier
                # censé être repris à l'identique ne l'était plus.
                lgs.append((r["CompteNum"], round(deb, 2), round(cre, 2),
                            r["EcritureLib"],
                            {"comp_aux_num": r["CompAuxNum"],
                             "comp_aux_lib": r["CompAuxLib"],
                             "ecriture_let": r["EcritureLet"],
                             "date_let": _date_iso(r["DateLet"],
                                                   f"DateLet de l'{ou}"),
                             "montant_devise": r["Montantdevise"],
                             "idevise": r["Idevise"]}))
            ecritures.inserer(conn, journal=r0["JournalCode"],
                              date=d, annee=annee,
                              libelle=r0["EcritureLib"] or "reprise",
                              piece_ref=r0["PieceRef"] or "NA",
                              piece_date=_date_iso(r0["PieceDate"],
                                                   f"PieceDate de l'{ou}"),
                              valid_date=_date_iso(r0["ValidDate"],
                                                   f"ValidDate de l'{ou}"),
                              num=num, commit=False, lignes=lgs)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"ecritures": len(par_ecriture), "normalisees": n_norm,
            "comptes_crees": comptes_crees, "renumerotees": renumeroter,
            "journaux_renommes": journaux_renommes}
