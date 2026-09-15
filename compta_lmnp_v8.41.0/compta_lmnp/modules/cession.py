# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
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
    lignes_dot, lignes_sortie = [], []
    total_dot, total_vnc, total_vb = 0.0, 0.0, 0.0
    for cid, lib, vb, duree, dms, c_immo, c_amort, amort in composants:
        cumul = 0.0
        if amort:
            dot, cumul_ouv = _dotation_prorata(vb, duree, dms, annee, d)
            if dot > 0.005:
                lignes_dot.append(("681120", dot, 0.0, f"DAA cession - {lib}"))
                lignes_dot.append((c_amort, 0.0, dot, f"DAA cession - {lib}"))
                total_dot += dot
            cumul = round(cumul_ouv + dot, 2)
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
