# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Reprise de PLUSIEURS exercices depuis leurs FEC.

Pourquoi plusieurs plutôt qu'un
-------------------------------
Un FEC isolé est une photographie : on le rejoue, on obtient un exercice,
et rien ne dit s'il est cohérent avec ce qui l'entoure. Plusieurs FEC
consécutifs donnent un FILM, et le film se vérifie tout seul — trois
contrôles deviennent possibles, qu'un fichier unique rend impossibles :

1. JONCTION DES BILANS. Le solde de clôture de chaque compte de bilan en
   année N doit se retrouver à l'ouverture de N+1. Un écart signale une
   écriture ajoutée après coup dans l'exercice précédent, ou un fichier
   qui n'est pas la version finale — c'est le défaut le plus fréquent
   d'une migration, et le plus silencieux.

2. AMORTISSEMENTS. Les dotations sont déterministes : à partir des
   composants, le plan se recalcule. Avec trois années de dotations
   réelles, on vérifie que le plan du logiciel reproduit celui du
   prestataire précédent — le même contrôle que le « test en or », mais
   appliqué au dossier de l'utilisateur.

3. CONTINUITÉ. Numérotation dense dans chaque exercice, dates dans les
   bornes, aucun trou d'année dans la série reprise.

Ces contrôles sont des OBSERVATIONS, jamais des refus : un écart peut
être parfaitement légitime (changement de durée, composant ajouté,
régularisation). Le rôle du logiciel est de le montrer, pas de trancher.
"""
from __future__ import annotations

import re
import sqlite3

import fec_io

MOTIF_ANNEE = re.compile(r"(20\d{2})")


def annee_du_fec(chemin: str) -> int | None:
    """Année de l'exercice, DÉDUITE du contenu et non du nom de fichier.

    Le nom est une convention (SIREN + date de clôture) que rien ne
    garantit ; les dates d'écriture, elles, sont dans le fichier. On prend
    l'année majoritaire : une écriture d'à-nouveau peut porter une date de
    l'exercice précédent sans que cela change l'exercice concerné.
    """
    entete, lignes = fec_io.lire_brut(chemin)
    if not entete:
        return None
    try:
        i = entete.index("EcritureDate")
    except ValueError:
        return None
    comptes: dict[str, int] = {}
    for ligne in lignes:
        if len(ligne) <= i:
            continue
        m = MOTIF_ANNEE.match((ligne[i] or "").strip())
        if m:
            comptes[m.group(1)] = comptes.get(m.group(1), 0) + 1
    if not comptes:
        return None
    return int(max(comptes, key=lambda a: comptes[a]))


JOURNAL_A_NOUVEAUX = "AN"


def _balance_bilan(chemin: str, ouverture: bool = False) -> dict[str, float]:
    """Soldes des comptes de BILAN (classes 1 à 5).

    Deux lectures possibles, et il faut les distinguer — c'est tout
    l'objet du contrôle de jonction :
      - CLÔTURE (défaut) : tout le fichier, soit la situation au 31/12 ;
      - OUVERTURE : les seules écritures d'à-nouveaux, soit la situation
        au 1er janvier telle que le prestataire l'a reprise.
    Comparer deux clôtures successives n'aurait aucun sens : leur écart
    est simplement l'activité de l'année.

    Les classes 6 et 7 sont exclues : elles se soldent à la clôture et
    n'ont pas à se retrouver à l'ouverture suivante.
    """
    entete, lignes = fec_io.lire_brut(chemin)
    if not entete:
        return {}
    idx = {c: n for n, c in enumerate(entete)}
    soldes: dict[str, float] = {}
    for ligne in lignes:
        if len(ligne) < len(fec_io.COLONNES):
            continue
        if ouverture and (ligne[idx["JournalCode"]] or "").strip().upper() \
                != JOURNAL_A_NOUVEAUX:
            continue
        compte = (ligne[idx["CompteNum"]] or "").strip()
        if not compte or compte[0] not in "12345":
            continue
        # Le RÉSULTAT DE L'EXERCICE (compte 12) est exclu : il naît aux
        # à-nouveaux de N+1, puis se solde par affectation au compte de
        # l'exploitant. Il figure donc à l'ouverture sans figurer à la
        # clôture précédente — et le comparer produirait un faux écart à
        # chaque jonction (constaté sur trois exercices réels).
        if compte.startswith("12"):
            continue
        try:
            v = fec_io.nombre(ligne[idx["Debit"]]) - fec_io.nombre(ligne[idx["Credit"]])
        except ValueError:
            continue
        soldes[compte] = round(soldes.get(compte, 0.0) + v, 2)
    return {c: v for c, v in soldes.items() if abs(v) >= 0.005}


def ordonner(chemins: list[str]) -> list[dict]:
    """Classe les fichiers par année et signale ce qui cloche.

    L'ordre est IMPOSÉ par les données, pas par l'ordre de sélection :
    rejouer 2025 avant 2023 produirait des à-nouveaux absurdes, et
    l'utilisateur n'a aucune raison de connaître cette contrainte.
    """
    out = []
    for chemin in chemins:
        annee = annee_du_fec(chemin)
        erreurs = []
        if annee is None:
            erreurs.append("année indéterminable : le fichier ne contient "
                           "aucune date d'écriture lisible.")
        out.append({"chemin": chemin, "annee": annee, "erreurs": erreurs})
    connues = [x for x in out if x["annee"]]
    doublons = {x["annee"] for x in connues
                if sum(1 for y in connues if y["annee"] == x["annee"]) > 1}
    for x in out:
        if x["annee"] in doublons:
            x["erreurs"].append(
                f"deux fichiers portent l'exercice {x['annee']} : gardez "
                "la version définitive.")
    return sorted(out, key=lambda x: (x["annee"] is None, x["annee"] or 0))


def controler_jonctions(fichiers: list[dict], tolerance: float = 0.01) -> list[dict]:
    """Le bilan de clôture de N se retrouve-t-il à l'ouverture de N+1 ?"""
    obs = []
    connus = [f for f in fichiers if f["annee"]]
    for prec, suiv in zip(connus, connus[1:]):
        if suiv["annee"] != prec["annee"] + 1:
            obs.append({
                "type": "trou",
                "message": f"Il manque l'exercice {prec['annee'] + 1} entre "
                           f"{prec['annee']} et {suiv['annee']}. La reprise "
                           "reste possible, mais la jonction des bilans ne "
                           "peut pas être vérifiée sur cet intervalle."})
            continue
        # Clôture de N contre OUVERTURE de N+1 : c'est la seule
        # comparaison qui ait un sens.
        avant = _balance_bilan(prec["chemin"])
        apres = _balance_bilan(suiv["chemin"], ouverture=True)
        if not apres:
            obs.append({
                "type": "info",
                "message": f"Le FEC {suiv['annee']} ne comporte pas de "
                           "journal d'à-nouveaux : la jonction des bilans "
                           "ne peut pas être vérifiée."})
            continue
        # Deux catégories, et les confondre revenait à mentir : ce qui
        # dépasse la tolérance, et ce qui ne la dépasse PAS tout en étant
        # non nul. Le message annonçait « les bilans se raccordent au
        # centime » dès qu'aucun écart ne dépassait le seuil — alors que le
        # seuil vaut précisément un centime, et qu'un décalage d'un centime
        # sur deux comptes était donc approuvé sous ce libellé. Une
        # tolérance est un choix de contrôle légitime ; la présenter comme
        # une égalité ne l'est pas.
        ecarts, tolères = [], []
        for compte in sorted(set(avant) | set(apres)):
            d = round(apres.get(compte, 0.0) - avant.get(compte, 0.0), 2)
            if abs(d) > tolerance:
                ecarts.append((compte, avant.get(compte, 0.0),
                               apres.get(compte, 0.0), d))
            elif d:
                tolères.append((compte, avant.get(compte, 0.0),
                                apres.get(compte, 0.0), d))
        if not ecarts and not tolères:
            obs.append({
                "type": "ok",
                "message": f"Jonction {prec['annee']} → {suiv['annee']} : "
                           "les bilans se raccordent exactement."})
        elif not ecarts:
            detail = " ; ".join(f"{c} : {a:.2f} → {b:.2f} ({d:+.2f})"
                                for c, a, b, d in tolères[:6])
            obs.append({
                "type": "tolere", "ecarts_toleres": tolères,
                "message": f"Jonction {prec['annee']} → {suiv['annee']} : "
                           f"{len(tolères)} compte(s) ne se raccordent pas "
                           f"exactement, mais l'écart reste sous la "
                           f"tolérance de {tolerance:.2f} € et n'est pas "
                           f"signalé comme une rupture. {detail}"
                           + (" …" if len(tolères) > 6 else "")
                           + " À vérifier tout de même si ces comptes "
                             "doivent se raccorder au centime."})
        else:
            detail = " ; ".join(
                f"{c} : {a:.2f} → {b:.2f} ({d:+.2f})"
                for c, a, b, d in ecarts[:6])
            obs.append({
                "type": "ecart", "ecarts": ecarts,
                "message": f"Jonction {prec['annee']} → {suiv['annee']} : "
                           f"{len(ecarts)} compte(s) ne se raccordent pas. "
                           f"{detail}"
                           + (" …" if len(ecarts) > 6 else "")
                           + " Cela arrive quand une écriture a été ajoutée "
                             "après coup dans l'exercice précédent, ou quand "
                             "le fichier n'est pas la version définitive."})
    return obs


COMPTES_DOTATION = ("6811", "6812")


def dotations_du_fec(chemin: str) -> float:
    """Dotation aux amortissements comptabilisée dans l'exercice."""
    entete, lignes = fec_io.lire_brut(chemin)
    if not entete:
        return 0.0
    idx = {c: n for n, c in enumerate(entete)}
    total = 0.0
    for ligne in lignes:
        if len(ligne) < len(fec_io.COLONNES):
            continue
        compte = (ligne[idx["CompteNum"]] or "").strip()
        if not compte.startswith(COMPTES_DOTATION):
            continue
        try:
            total += (fec_io.nombre(ligne[idx["Debit"]])
                      - fec_io.nombre(ligne[idx["Credit"]]))
        except ValueError:
            continue
    return round(total, 2)


def controler_amortissements(conn: sqlite3.Connection,
                             fichiers: list[dict]) -> list[dict]:
    """Le plan du logiciel reproduit-il les dotations réellement passées ?

    C'est l'autocontrôle le plus utile d'une migration : il confronte le
    calcul du logiciel à celui d'un professionnel, sur le dossier de
    l'utilisateur — exactement ce que fait le « test en or » du projet,
    mais avec les données de celui qui migre.
    """
    import amortissement
    obs = []
    for f in fichiers:
        if not f["annee"]:
            continue
        reel = dotations_du_fec(f["chemin"])
        try:
            plan = round(sum(d["dotation"]
                             for d in amortissement.dotations_exercice(
                                 conn, f["annee"])), 2)
        except Exception as exc:
            # Ne JAMAIS avaler l'exception en silence : une date de mise en
            # service vide sur un seul composant faisait taire le contrôle
            # sur TOUTES les années du dossier.
            obs.append({
                "type": "info", "annee": f["annee"],
                "message": f"{f['annee']} : le plan d'amortissement n'a pas "
                           f"pu être recalculé ({exc}). Vérifiez les dates "
                           "de mise en service et les durées de vos "
                           "composants — le contrôle est resté muet sur "
                           "cette année."})
            continue
        if reel <= 0 and plan <= 0:
            continue
        if reel <= 0:
            # Le cas le plus dangereux, et celui où le contrôle se taisait :
            # le FEC ne porte AUCUNE dotation alors que le plan en calcule
            # une. Typiquement un bien acquis en fin d'année N, mis en
            # location en N+1, que le cabinet n'a pas encore amorti. Le
            # logiciel amortira dès N, et son cumul dépassera durablement
            # celui repris par les à-nouveaux.
            obs.append({
                "type": "ecart", "annee": f["annee"], "ecart": plan,
                "message": f"{f['annee']} : le FEC ne porte AUCUNE dotation, "
                           f"alors que le plan recalculé en donne "
                           f"{plan:.2f} €. Si votre ancien prestataire n'a "
                           "pas amorti cette année-là, avancez la date de "
                           "mise en service de vos composants à l'exercice "
                           "où il a commencé — sinon vos amortissements "
                           "cumulés dépasseront définitivement les siens."})
            continue
        if plan <= 0:
            obs.append({
                "type": "info", "annee": f["annee"],
                "message": f"{f['annee']} : {reel:.2f} € de dotations dans le "
                           "FEC, mais aucun composant n'est encore enregistré. "
                           "Saisissez vos immobilisations pour que le plan "
                           "puisse être confronté."})
            continue
        ecart = round(plan - reel, 2)
        if abs(ecart) <= max(1.0, 0.005 * reel):
            obs.append({
                "type": "ok", "annee": f["annee"],
                "message": f"{f['annee']} : dotations {reel:.2f} € — le plan "
                           "recalculé par le logiciel donne le même montant."})
        else:
            obs.append({
                "type": "ecart", "annee": f["annee"], "ecart": ecart,
                "message": f"{f['annee']} : le FEC porte {reel:.2f} € de "
                           f"dotations, le plan recalculé en donne "
                           f"{plan:.2f} € ({ecart:+.2f} €). Vérifiez les "
                           "durées et les dates de mise en service de vos "
                           "composants — un écart durable fausserait toutes "
                           "les liasses à venir."})
    return obs
