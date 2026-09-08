# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Jalon J0 — Reprise / migration depuis un prestataire externe.

Lit un FEC de clôture (ex. 2025), calcule la balance des comptes de bilan,
et génère dans la base l'écriture d'à-nouveaux (AN) de l'exercice suivant,
suivie de l'OD d'affectation du résultat — exactement comme le fait un cabinet.

Le logiciel REMPLACE le prestataire externe : ce module est le pont qui garantit que le premier
bilan d'ouverture se réconcilie au centime avec le dernier bilan déclaré.
"""
from __future__ import annotations
import sqlite3

import ecritures
from collections import defaultdict

import fec_io

CENT = 0.005  # tolérance d'arrondi (demi-centime)


def lire_balance_fec(fec_path: str) -> dict[str, float]:
    """Solde net (débit - crédit) par compte, sur tout le fichier.

    Lecture par fec_io (socle commun aux trois consommateurs de FEC).
    Sémantique historique préservée : une ligne porte une balance dès
    qu'elle atteint la colonne Credit (13 champs) — plus tolérant que le
    rejeu, qui exige les 18 colonnes, car la balance sert aussi à
    contrôler des fichiers partiels."""
    bal: dict[str, float] = defaultdict(float)
    _entete, lignes = fec_io.lire_brut(fec_path)
    for r in lignes:
        if len(r) < 13:
            continue
        bal[r[4]] += fec_io.nombre(r[11]) - fec_io.nombre(r[12])
    return dict(bal)


def lire_balance_interne(conn: sqlite3.Connection, annee: int) -> dict[str, float]:
    """
    Solde net (débit - crédit) par compte, calculé DEPUIS LA BASE sur les
    écritures de l'exercice `annee`. Comme l'AN de cet exercice porte déjà
    tout l'historique antérieur, cette balance est cumulative depuis
    l'origine — strictement équivalente à la lecture du FEC de clôture.
    """
    rows = conn.execute(
        "SELECT l.compte_num, ROUND(SUM(l.debit - l.credit), 2) "
        "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.exercice_annee = ? GROUP BY l.compte_num", (annee,)
    ).fetchall()
    return {compte: solde for compte, solde in rows}


def construire_an(conn: sqlite3.Connection, fec_path: str, annee_cible: int) -> None:
    """Insère l'AN d'ouverture `annee_cible` + l'OD d'affectation du résultat,
    depuis un FEC de clôture EXTERNE (migration les acteurs payants actuels)."""
    _construire_an_depuis_balance(conn, lire_balance_fec(fec_path), annee_cible)


def construire_an_interne(conn: sqlite3.Connection, annee_cible: int) -> dict:
    """
    Reprise INTERNE : clôture N-1 → ouverture N sans fichier externe.
    Lit la balance de clôture de l'exercice précédent directement dans la
    base et génère l'AN + l'OD d'affectation, exactement comme la reprise FEC.

    Garde-fous :
      - l'exercice N-1 doit exister et être CLOS ;
      - aucun AN ne doit déjà exister sur l'exercice cible.
    Renvoie {'annee_source', 'resultat_reporte', 'nb_comptes'}.
    """
    annee_source = annee_cible - 1
    ex = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                      (annee_source,)).fetchone()
    if ex is None:
        raise ValueError(f"Aucun exercice {annee_source} en base : "
                         "reprise interne impossible.")
    if ex[0] != "clos":
        raise ValueError(f"L'exercice {annee_source} n'est pas clôturé : "
                         "clôturez-le avant d'ouvrir avec reprise des à-nouveaux.")
    deja = conn.execute(
        "SELECT COUNT(*) FROM ecriture WHERE exercice_annee=? AND journal_code='AN'",
        (annee_cible,)).fetchone()[0]
    if deja:
        raise ValueError(f"L'exercice {annee_cible} contient déjà des à-nouveaux.")

    bal = lire_balance_interne(conn, annee_source)
    resultat = -sum(v for n, v in bal.items() if n[0] in "67")
    nb = _construire_an_depuis_balance(conn, bal, annee_cible)
    return {"annee_source": annee_source,
            "resultat_reporte": round(resultat, 2), "nb_comptes": nb}


def _construire_an_depuis_balance(conn: sqlite3.Connection,
                                  bal: dict[str, float], annee_cible: int) -> int:
    """Mécanique commune : balance de clôture → écriture AN + OD d'affectation."""
    date_ouv = f"{annee_cible}-01-01"

    # Comptes de bilan = classes 1 à 5, hors résultat 120000 traité à part.
    #
    # Les classes 3 et 5 étaient omises. La 5 est celle de la TRÉSORERIE :
    # tout dossier tenu avec un compte bancaire dédié — le cas ordinaire
    # chez un cabinet — produisait donc une écriture d'à-nouveaux
    # déséquilibrée du montant exact du solde bancaire, et la reprise
    # s'arrêtait sur « Écriture déséquilibrée », en accusant une écriture
    # que l'utilisateur n'avait jamais saisie. Aucune migration d'un
    # dossier bancarisé n'était possible.
    #
    # `migration_fec._balance_bilan` retenait déjà les classes 1 à 5 : les
    # deux modules ne s'accordaient pas sur ce qu'est un compte de bilan.
    classe = {n: n[0] for n in bal}
    bilan = {n: v for n, v in bal.items()
             if classe[n] in "12345" and n != "120000" and abs(v) > CENT}

    # Résultat comptable = -(somme nette des comptes de charges/produits).
    resultat = -sum(v for n, v in bal.items() if classe[n] in "67")

    # Garde-fou : un second appel doublerait le bilan d'ouverture, en
    # silence et de façon équilibrée — donc invisible. `construire_an_interne`
    # vérifiait déjà ce point ; la reprise depuis un FEC externe, non.
    deja = conn.execute(
        "SELECT COUNT(*) FROM ecriture WHERE exercice_annee=? "
        "AND journal_code='AN'", (annee_cible,)).fetchone()[0]
    if deja:
        raise ValueError(
            f"L'exercice {annee_cible} a déjà ses à-nouveaux "
            f"({deja} écriture(s) au journal AN). Les reconstruire "
            "doublerait le bilan d'ouverture. Supprimez d'abord l'exercice "
            "si vous voulez recommencer la reprise.")

    # Les comptes du cabinet ne figurent pas au plan livré : on les crée
    # avant d'écrire, sinon l'insertion échoue sur une contrainte de clé
    # étrangère brute, qui ne nomme même pas le compte fautif.
    fec_io.assurer_comptes(conn, [(n, n) for n in bilan] + [("120000", "Résultat")])

    # --- Écriture AN -------------------------------------------------------
    lignes: list[tuple] = []
    for compte, net in sorted(bilan.items()):
        lignes.append((compte, round(net, 2) if net > 0 else 0.0,
                       round(-net, 2) if net < 0 else 0.0))
    # Le résultat de l'exercice clos est porté par 120000 (perte = débit).
    if abs(resultat) > CENT:
        lignes.append(("120000",
                       round(-resultat, 2) if resultat < 0 else 0.0,
                       round(resultat, 2) if resultat > 0 else 0.0,
                       "A Nouveaux - résultat reporté"))
    r_an = ecritures.inserer(conn, journal="AN", date=date_ouv, annee=annee_cible,
                             libelle="A Nouveaux", lignes=lignes, commit=False)

    # --- OD d'affectation du résultat (120000 -> 108000) -------------------
    montant = round(abs(resultat), 2)
    if resultat < 0:   # perte : on débite 108000, on crédite 120000
        aff = [("108000", montant, 0.0), ("120000", 0.0, montant)]
    else:              # bénéfice : on crédite 108000, on débite 120000
        aff = [("108000", 0.0, montant), ("120000", montant, 0.0)]
    ecritures.inserer(conn, journal="OD", date=date_ouv, annee=annee_cible,
                      libelle="Affectation du résultat", lignes=aff,
                      num=r_an["ecriture_num"] + 1, commit=False)
    conn.commit()
    return len(bilan)


def controle_equilibre(conn: sqlite3.Connection, annee: int) -> tuple[float, float]:
    """Renvoie (total_debit, total_credit) des écritures d'un exercice."""
    row = conn.execute(
        "SELECT COALESCE(SUM(l.debit),0), COALESCE(SUM(l.credit),0) "
        "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.exercice_annee = ?", (annee,),
    ).fetchone()
    return round(row[0], 2), round(row[1], 2)


def ouvrir_exercice(conn: sqlite3.Connection, annee: int,
                    avec_reprise: bool = True) -> None:
    """Ouvre l'exercice `annee` (01/01 → 31/12) ; si l'exercice précédent est
    clos et `avec_reprise` est vrai, construit les à-nouveaux internes.
    Point d'entrée UNIQUE d'ouverture d'exercice (interface web, CLI, tests)."""
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                 "VALUES (?, ?, ?, 'ouvert')",
                 (annee, f"{annee}-01-01", f"{annee}-12-31"))
    conn.commit()
    if avec_reprise:
        prec = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                            (annee - 1,)).fetchone()
        if prec and prec[0] == "clos":
            construire_an_interne(conn, annee)
