# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Cession d'un bien — sortie comptable et fiscale d'un logement.

Traduction comptable (pratique de la profession, identique à celle des logiciels du marché) :
  1. dotation COMPLÉMENTAIRE prorata temporis, du 1er janvier à la date de
     cession (un bien s'amortit jusqu'à sa sortie) ;
  2. sortie de chaque composant : débit 28x (amortissements cumulés),
     débit 675000 (valeur nette comptable), crédit 2x (valeur brute) —
     le terrain, non amortissable, sort en VNC pleine ;
  3. encaissement du prix : débit 108000 (exploitant), crédit 775000.

Traitement FISCAL (spécificité LMNP) : la plus-value de cession relève du
régime des PARTICULIERS (art. 150 U CGI), calculée et déclarée par le
notaire (2048-IMM) — elle est donc NEUTRALISÉE dans le résultat BIC :
le produit 775000 est déduit, la VNC 675000 est réintégrée (retraitements
extra-comptables à la clôture, cf. fiscal.cloturer). Le stock 39 C attaché
au bien cédé est définitivement perdu (ligne G' de l'état SUIV39C) : la
ventilation par bien (v7.6.0) le rend traçable.

⚠️ Depuis la loi de finances 2025, les amortissements déduits sont
réintégrés dans le calcul de la plus-value des particuliers (art. 150 VB) —
ce calcul appartient au notaire ; le pense-bête le rappelle.
"""
from __future__ import annotations

import math

import datetime
import sqlite3

import amortissement
import ecritures

COMPTE_VNC = "675000"       # Valeurs comptables des éléments d'actif cédés
COMPTE_PRODUIT = "775000"   # Produits des cessions d'éléments d'actif
CONTREPARTIE = "108000"     # Exploitant


def assurer_schema(conn: sqlite3.Connection) -> None:
    """Colonnes et comptes nécessaires, créés à la volée (activation en cours
    de vie, sans migration — même approche que le suivi 39 C par bien)."""
    for table, colonne in (("bien", "date_cession"), ("composant", "date_sortie")):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} TEXT")
        except sqlite3.OperationalError:
            pass                                    # colonne déjà présente
    for numero, libelle, type_, classe in (
            (COMPTE_VNC, "Valeurs comptables des éléments d'actif cédés",
             "charge", 6),
            (COMPTE_PRODUIT, "Produits des cessions d'éléments d'actif",
             "produit", 7)):
        conn.execute("INSERT OR IGNORE INTO compte (numero, libelle, type, "
                     "classe) VALUES (?,?,?,?)", (numero, libelle, type_, classe))


def _dotation_prorata(vb, duree, dms, annee, date_cession) -> tuple[float, float]:
    """(dotation prorata de l'année de cession, cumul au 1er janvier).

    Prorata en JOURS RÉELS du 1er janvier à la date de cession incluse
    (même convention que la mise en service, cf.
    amortissement.fraction_prorata) — un prorata au mois surévaluait la
    dotation de sortie. Plafonnée à la VNC restante."""
    # On calcule le CUMUL À LA DATE DE CESSION, puis on retranche celui du
    # 1er janvier. L'ancienne méthode multipliait la dotation de l'année —
    # déjà proratisée par le plan — par la fraction 1er janvier → cession :
    # un second prorata appliqué à un montant qui l'était déjà.
    #
    # L'erreur allait dans les DEUX SENS. Pour un composant mis en service
    # en cours d'année de cession, la dotation du plan couvrait déjà la
    # seule période de détention, et la réduire encore la sous-évaluait…
    # sauf que le plan démarrait au 1er janvier, d'où une SUR-évaluation
    # (627,05 € au lieu de 586,30 € sur un cas éprouvé). Pour une dernière
    # annuité tronquée par la fin de vie, elle sous-évaluait de moitié
    # (245,91 € au lieu de 493,15 €).
    if not duree or duree <= 0:
        return 0.0, 0.0
    _, cumul_ouv, _ = amortissement.etat(vb, duree, dms, annee - 1)
    vnc_ouv = round(float(vb) - cumul_ouv, 2)
    if vnc_ouv <= 0.005:
        return 0.0, cumul_ouv
    # Prorata de l'ANNUITÉ PLEINE sur la seule période de détention de
    # l'exercice de cession — du 1er janvier, ou de la mise en service si
    # elle est postérieure, jusqu'à la date de cession incluse.
    # `fraction_prorata` est intra-annuelle et plafonnée à 1 : elle ne
    # s'applique donc qu'à l'intérieur d'un exercice.
    annuite = float(vb) / float(duree)
    debut = max(str(dms or f"{annee}-01-01"), f"{annee}-01-01")
    fraction = float(amortissement.fraction_prorata(debut,
                                                    date_cession.isoformat()))
    dot = round(annuite * fraction, 2)
    # Plafonné à ce qu'il reste à amortir : la dernière annuité d'un plan
    # arrivé à son terme est tronquée, et il ne faut pas la dépasser.
    return max(0.0, min(dot, vnc_ouv)), cumul_ouv


def _cumuls_a_solder(conn: sqlite3.Connection, annee: int,
                     composants) -> dict[int, float]:
    """Cumul d'amortissement à SOLDER par composant, à l'ouverture de
    l'exercice de cession — lu dans les COMPTES, pas dans le plan.

    La sortie d'actif reprenait le cumul du plan théorique. Or ce plan est
    recalculé depuis la durée et la date actuelles du composant, et rien ne
    garantit qu'il décrive ce qui a été comptabilisé : un historique repris
    d'un cabinet, ou une durée corrigée après coup, le démentent. Sur un
    composant de 12 000 € portant 3 000 € d'amortissements repris pour
    1 200 € au plan, la sortie soldait 1 200 € — laissant 1 800 €
    d'amortissements en compte pour un actif qui n'existe plus, et
    gonflant d'autant la valeur nette passée en charge de cession.

    Solder, c'est ramener un compte à zéro : le montant à solder est donc
    celui qui s'y trouve, pas celui qu'on aurait aimé y trouver.

    Deux cas où l'on ne peut pas isoler ce montant :
      - la base ne permet pas de lire le solde (compte absent, exercice
        sans historique) : on retombe sur le plan, comportement d'origine ;
      - le compte sert aussi à des composants qui NE SONT PAS cédés, et le
        solde ne concorde pas avec le plan. Ce qui excède ne peut alors
        être attribué ni aux uns ni aux autres : on refuse plutôt que de
        trancher à la place de l'utilisateur.
    """
    par_compte: dict[str, list] = {}
    for cid, lib, vb, duree, dms, _ci, c_amort, amort in composants:
        if amort and c_amort:
            par_compte.setdefault(c_amort, []).append(
                (cid, lib, vb, duree, dms))
    cumuls = {c[0]: 0.0 for c in composants}
    for c_amort, membres in par_compte.items():
        theoriques = {}
        for cid, _lib, vb, duree, dms in membres:
            _dot, cumul_ouv = _dotation_prorata(vb, duree, dms, annee,
                                                datetime.date(annee, 1, 1))
            theoriques[cid] = round(cumul_ouv, 2)
        total_theorique = round(sum(theoriques.values()), 2)
        # Le solde tel qu'il se présente AVANT toute écriture de cession —
        # d'où l'appel en tête de `ceder_bien`.
        deja = amortissement._cumul_comptabilise(conn, c_amort, annee)
        if deja is None:
            cumuls.update(theoriques)
            continue
        # Les composants du MÊME compte qui restent au bilan gardent leur
        # part : elle ne se solde pas avec ce bien.
        restants = conn.execute(
            "SELECT id, valeur_brute, duree_annees, date_mise_service "
            "FROM composant WHERE compte_amort=? AND amortissable=1 "
            "AND (date_sortie IS NULL OR date_sortie='') "
            f"AND id NOT IN ({','.join('?' * len(membres))})",
            (c_amort, *[m[0] for m in membres])).fetchall()
        part_restants = 0.0
        for _cid, vb, duree, dms in restants:
            _dot, cumul_ouv = _dotation_prorata(vb, duree, dms, annee,
                                                datetime.date(annee, 1, 1))
            part_restants = round(part_restants + cumul_ouv, 2)
        a_solder = round(deja - part_restants, 2)
        ecart = round(a_solder - total_theorique, 2)
        seuil = max(1.0, 0.01 * sum(float(m[2]) for m in membres))
        if restants and abs(ecart) > seuil:
            raise ValueError(
                f"Cession impossible en l'état : le compte {c_amort} porte "
                f"{deja:.2f} € d'amortissements, alors que le plan en prévoit "
                f"{round(total_theorique + part_restants, 2):.2f} € pour "
                "l'ensemble des composants qui l'utilisent. Comme ce compte "
                "sert aussi à des composants qui ne sont pas cédés, l'écart "
                f"de {ecart:.2f} € ne peut être attribué ni aux uns ni aux "
                "autres. Rapprochez les amortissements de ce compte avant de "
                "céder — ou donnez aux composants de ce bien leur propre "
                "compte d'amortissement.")
        if abs(ecart) <= seuil:
            cumuls.update(theoriques)           # plan et comptes concordent
            continue
        # Répartition du cumul RÉEL entre les composants cédés du compte,
        # au prorata de leur cumul théorique — exacte lorsqu'ils ne sont
        # qu'un, ce qui est le cas courant.
        if total_theorique > 0.005:
            reparti = 0.0
            for i, (cid, *_r) in enumerate(membres):
                part = (round(a_solder - reparti, 2) if i == len(membres) - 1
                        else round(a_solder * theoriques[cid]
                                   / total_theorique, 2))
                reparti = round(reparti + part, 2)
                cumuls[cid] = part
        else:
            bruts = sum(float(m[2]) for m in membres) or 1.0
            for cid, _lib, vb, *_r in membres:
                cumuls[cid] = round(a_solder * float(vb) / bruts, 2)
    return cumuls


def ceder_bien(conn: sqlite3.Connection, bien_id: int, date_cession: str,
               prix_cession: float, commit: bool = True) -> dict:
    """Passe toutes les écritures de cession du bien. Retourne le détail
    (dotation complémentaire, VNC totale, plus ou moins-value comptable)."""
    assurer_schema(conn)
    bien = conn.execute("SELECT libelle, date_cession FROM bien WHERE id=?",
                        (bien_id,)).fetchone()
    if bien is None:
        raise ValueError(f"Bien {bien_id} inconnu.")
    if bien[1]:
        raise ValueError(f"« {bien[0]} » est déjà cédé (le {bien[1]}).")
    try:
        d = datetime.date.fromisoformat(date_cession)
    except ValueError:
        raise ValueError(f"Date de cession invalide : {date_cession!r} "
                         "(format AAAA-MM-JJ).") from None
    annee = d.year
    # Une vente ne peut pas précéder l'entrée du bien au patrimoine. Seule
    # la SYNTAXE de la date était contrôlée : une cession datée de la
    # veille de l'acquisition était acceptée, sortait 12 000 € d'actif,
    # enregistrait 15 000 € de produit sur une chronologie impossible — et
    # la liasse déclarait le tout conforme. Le logiciel ne peut pas deviner
    # laquelle des deux dates est fausse ; il peut refuser la combinaison.
    entree = conn.execute(
        "SELECT MIN(date_mise_service) FROM composant WHERE bien_id=? "
        "AND date_mise_service IS NOT NULL AND date_mise_service<>''",
        (bien_id,)).fetchone()[0]
    try:
        acquisition = conn.execute(
            "SELECT date_acquisition FROM bien WHERE id=?",
            (bien_id,)).fetchone()[0]
    except sqlite3.OperationalError:
        acquisition = None
    plus_ancienne = min(x for x in (entree, acquisition) if x) \
        if (entree or acquisition) else None
    if plus_ancienne and date_cession < plus_ancienne:
        raise ValueError(
            f"Cession datée du {date_cession}, antérieure à l'entrée du bien "
            f"dans le patrimoine ({plus_ancienne}). Un bien ne peut pas être "
            "vendu avant d'avoir été acquis : corrigez la date de vente, ou "
            "la date d'acquisition ou de mise en service si c'est elle qui "
            "est inexacte.")

    # `nan < 0` est FAUX, comme toute comparaison avec nan : le prix passait
    # ce contrôle, puis `nan > 0` était faux à son tour et aucune écriture de
    # produit n'était générée. La cession s'enregistrait quand même —
    # composants sortis, date de cession posée, 12 000 € d'actif disparus —
    # pour une demande qui n'avait pas de prix. Le rejet des valeurs non
    # finies du guichet d'écriture n'était jamais atteint, faute d'écriture.
    try:
        prix_cession = float(prix_cession)
    except (TypeError, ValueError):
        raise ValueError(f"Prix de cession invalide : {prix_cession!r} "
                         "(un montant en euros est attendu).") from None
    if not math.isfinite(prix_cession):
        raise ValueError("Le prix de cession doit être un montant chiffré "
                         "(valeur reçue : ni un nombre, ni un montant fini).")
    if prix_cession < 0:
        raise ValueError("Le prix de cession ne peut pas être négatif.")

    composants = conn.execute(
        "SELECT id, libelle, valeur_brute, duree_annees, date_mise_service, "
        "compte_immo, compte_amort, amortissable FROM composant "
        "WHERE bien_id=? AND (date_sortie IS NULL OR date_sortie='')",
        (bien_id,)).fetchall()
    if not composants:
        raise ValueError(f"« {bien[0]} » n'a aucun composant actif à sortir.")

    # 1. Dotation complémentaire prorata temporis (janvier → mois de cession).
    #    Le CUMUL À SOLDER, lui, se lit dans les comptes : voir
    #    `_cumuls_a_solder`, appelé avant toute insertion.
    cumuls = _cumuls_a_solder(conn, annee, composants)
    lignes_dot, lignes_sortie = [], []
    total_dot, total_vnc, total_vb = 0.0, 0.0, 0.0
    for cid, lib, vb, duree, dms, c_immo, c_amort, amort in composants:
        cumul = 0.0
        if amort:
            dot, _cumul_theorique_ouv = _dotation_prorata(vb, duree, dms,
                                                          annee, d)
            if dot > 0.005:
                lignes_dot.append(("681120", dot, 0.0, f"DAA cession - {lib}"))
                lignes_dot.append((c_amort, 0.0, dot, f"DAA cession - {lib}"))
                total_dot += dot
            cumul = round(cumuls[cid] + dot, 2)
        vnc = round(vb - cumul, 2)
        # 2. Sortie du composant : 28x + 675000 contre 2x (valeur brute).
        if cumul > 0.005:
            lignes_sortie.append((c_amort, cumul, 0.0, f"Sortie - {lib}"))
        if vnc > 0.005:
            lignes_sortie.append((COMPTE_VNC, vnc, 0.0, f"Sortie VNC - {lib}"))
        lignes_sortie.append((c_immo, 0.0, round(vb, 2), f"Sortie - {lib}"))
        total_vnc += vnc
        total_vb += vb

    # La référence de pièce PORTE L'IDENTIFIANT DU BIEN. Le suivi 39 C
    # devait retrouver la dotation de cession d'un bien pour lui attribuer
    # sa part du report ; il le faisait en comparant le LIBELLÉ des lignes
    # (« DAA cession - <composant> »), ce qui suppose des libellés uniques.
    # Deux biens meublés dont le composant s'appelle pareil — le cas le plus
    # ordinaire qui soit — et chaque bien cédé se voyait attribuer la
    # dotation de tous les autres : le stock conservé du bien restant
    # fondait d'autant. Un identifiant ne se déduit pas d'une description.
    if lignes_dot:
        ecritures.inserer(conn, journal="OD", date=date_cession, annee=annee,
                          piece_ref=f"DAA-CESSION-{bien_id}", commit=False,
                          libelle=f"Dotation complémentaire cession {bien[0]}",
                          lignes=lignes_dot)
    ecritures.inserer(conn, journal="OD", date=date_cession, annee=annee,
                      piece_ref=f"CESSION-{bien_id}", commit=False,
                      libelle=f"Sortie d'actif - cession {bien[0]}",
                      lignes=lignes_sortie)
    # 3. Prix de cession.
    prix = round(float(prix_cession), 2)
    if prix > 0:
        ecritures.inserer(conn, journal="OD", date=date_cession, annee=annee,
                          piece_ref=f"CESSION-{bien_id}", commit=False,
                          libelle=f"Prix de cession {bien[0]}",
                          lignes=[(CONTREPARTIE, prix, 0.0, "Prix de cession"),
                                  (COMPTE_PRODUIT, 0.0, prix, "Prix de cession")])

    conn.execute("UPDATE composant SET date_sortie=? WHERE bien_id=? AND (date_sortie IS NULL OR date_sortie='')",
                 (date_cession, bien_id))
    conn.execute("UPDATE bien SET date_cession=? WHERE id=?",
                 (date_cession, bien_id))
    if commit:
        conn.commit()
    return {"bien": bien[0], "dotation_complementaire": round(total_dot, 2),
            "valeur_brute_sortie": round(total_vb, 2),
            "vnc_sortie": round(total_vnc, 2), "prix_cession": prix,
            "pv_comptable": round(prix - total_vnc, 2)}
