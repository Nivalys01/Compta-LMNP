# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Jalon J4 — Moteur d'amortissement par composants.

Pour chaque composant : dotation annuelle = valeur_brute / durée, avec prorata
temporis l'année de mise en service et plafonnement la dernière année (la somme
des dotations ne peut dépasser la valeur brute). Le terrain ne s'amortit pas.

Génère l'écriture OD de clôture au 31/12 : pour chaque composant, une paire
681120 (débit) / 281xxx (crédit), au centime, comme le fait un cabinet.

⚠️ Les durées et la méthode (linéaire par composants) relèvent de choix fiscaux :
à faire valider par un expert-comptable.
"""
from __future__ import annotations
import datetime
import sqlite3

import ecritures
import plan_immo
from decimal import Decimal, ROUND_HALF_UP

CONTREPARTIE_DOTATION = "681120"   # Dotation aux amortissements (charge)


def _d(x) -> Decimal:
    return Decimal(str(x))


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fraction_prorata(debut: str, fin: str | None = None) -> Decimal:
    """
    Prorata temporis en JOURS RÉELS, base 365, jour de début inclus.

    Convention établie EMPIRIQUEMENT contre les liasses réelless offres payantes
    2023-2025 : elle reproduit les cumuls d'amortissement déclarés des
    13 composants, y compris les acquisitions en cours de mois (Huisseries
    Est du 11/03/2022, OUEST du 25/05/2022, Porte d'entrée du 26/10/2022)
    — là où un prorata au MOIS se trompait de 2 à 6 € par composant.
    Un prorata au mois surévalue l'amortissement d'une entrée de fin de
    mois : c'est un risque de redressement, pas une simple imprécision.

    `fin` par défaut = 31/12 de l'année de `debut` (année de mise en
    service) ; passer une date pour l'année de sortie (cession).
    Plafonné à 1 (années bissextiles).
    """
    d = datetime.date.fromisoformat(debut)
    f = datetime.date.fromisoformat(fin) if fin else datetime.date(d.year, 12, 31)
    jours = (f - d).days + 1                      # jour de début inclus
    if jours <= 0:
        return _d(0)
    return min(_d(jours) / _d(365), _d(1))


def duree_valide(brut) -> int | None:
    """Durée d'amortissement saisie : None (non amortissable), ou un entier
    strictement positif. Lève ValueError, avec le motif, sinon.

    Le champ était lu par `int(x) if x and x != "0" else None` : « -1 »
    passait donc la garde, le composant était créé `amortissable=1` avec un
    plan impossible, son acquisition était comptabilisée, aucune dotation
    n'était jamais générée et le tableau des immobilisations affichait un
    amortissement NÉGATIF. Une durée est un nombre d'années : ni négative,
    ni fractionnaire, ni démesurée.
    """
    brut = str(brut or "").strip().replace(",", ".")
    if not brut or brut == "0":
        return None
    try:
        duree = int(brut)
    except (TypeError, ValueError):
        raise ValueError(
            f"Durée d'amortissement invalide : « {brut} ». Indiquez un "
            "nombre entier d'années (ou 0 pour un bien non amortissable, "
            "comme un terrain).") from None
    if duree < 0:
        raise ValueError(
            f"Durée d'amortissement négative : {duree} an(s). Un "
            "amortissement se répartit sur des années à venir. Indiquez la "
            "durée d'utilisation prévue, ou 0 si le bien ne s'amortit pas.")
    if duree > 120:
        raise ValueError(
            f"Durée d'amortissement de {duree} ans : au-delà de 120 ans, "
            "c'est très probablement une erreur de saisie. Les durées "
            "usuelles vont de 5 ans (mobilier) à 50 ans (gros œuvre).")
    return duree or None


def plan(valeur_brute: float, duree_annees: int, date_mise_service: str) -> list[tuple[int, float]]:
    """Déroule le plan : liste de (année, dotation), de la mise en service à
    l'épuisement de la valeur brute.

    Deux invariants, que la rédaction précédente ne tenait pas toujours :

    1. **La somme des annuités vaut EXACTEMENT la valeur brute.** L'annuité
       était calculée une fois pour toutes et arrondie au centime ; sur une
       valeur que la durée ne divise pas rond, le reliquat n'était nulle
       part. Pire, une annuité inférieure à un demi-centime — 0,24 € sur
       cinquante ans — s'arrondissait à 0,00 €, la boucle n'avançait plus,
       le garde-fou anti-boucle la coupait, et le plan rendu était vide :
       la valeur n'était JAMAIS amortie, sans le moindre signal. Le plan
       descend donc au centime, et la dernière annuité solde le reste.

    2. **Le plan ne dure pas plus que sa durée** — plus une année lorsque
       l'entrée en cours d'année reporte un reliquat. Le cumul des arrondis
       pouvait ajouter une année de 0,01 € après les cinquante prévues.
    """
    valeur = _d(valeur_brute)
    if valeur <= 0 or not duree_annees or duree_annees <= 0:
        return []                      # plan impossible : rien plutôt que faux
    annuelle = max(_q(valeur / _d(duree_annees)), _d("0.01"))
    fraction = fraction_prorata(date_mise_service)
    an0 = int(date_mise_service[:4])
    # Une mise en service au 1er janvier consomme l'année entière : le plan
    # tient alors dans sa durée. Sinon, la fraction non consommée la
    # première année se retrouve sur une année supplémentaire.
    n_annees = duree_annees + (0 if fraction >= 1 else 1)

    out: list[tuple[int, float]] = []
    cumul = _d("0")
    for i in range(n_annees):
        dot = _q(annuelle * fraction) if i == 0 else annuelle
        if i == n_annees - 1 or cumul + dot >= valeur:
            dot = valeur - cumul       # la dernière annuité solde le plan
        if dot <= 0:
            break
        out.append((an0 + i, float(dot)))
        cumul += dot
        if cumul >= valeur:
            break
    return out


def etat(valeur_brute, duree_annees, date_mise_service, annee) -> tuple[float, float, float]:
    """Renvoie (dotation_de_l_annee, cumul_fin, vnc_fin) pour une année donnée."""
    cumul = 0.0
    dotation = 0.0
    for a, d in plan(valeur_brute, duree_annees, date_mise_service):
        if a <= annee:
            cumul += d
            if a == annee:
                dotation = d
    vnc = round(float(valeur_brute) - cumul, 2)
    return round(dotation, 2), round(cumul, 2), vnc


def dotations_exercice(conn: sqlite3.Connection, annee: int, *,
                       a_comptabiliser: bool = False) -> list[dict]:
    """Dotation de l'exercice par composant amortissable (dotation > 0 seule).

    DEUX LECTURES, et les confondre a coûté cher :

    - par défaut, **ce que le plan prévoit pour l'exercice**, mesuré depuis
      le cumul à son OUVERTURE. C'est une vue stable : elle donne la même
      réponse avant et après que la dotation ait été passée, ce dont
      dépendent tous les lecteurs — contrôles, liasse, projection fiscale ;
    - avec `a_comptabiliser=True`, **ce qu'il reste à écrire**, mesuré
      depuis le cumul tel qu'il se présente AU MOMENT de clôturer. Seule la
      génération de l'écriture s'en sert : c'est ainsi qu'une dotation déjà
      saisie à la main dans l'exercice n'en fait plus générer une seconde.

    Avant une génération, les deux vues coïncident. Après, la première
    continue de dire ce que l'exercice doit porter, la seconde qu'il ne
    reste rien à écrire.
    """
    # Les composants SORTIS (bien cédé) ne reçoivent plus de dotation de
    # clôture : leur dotation prorata a été passée à la cession.
    # Les dates sont stockées en TEXT AAAA-MM-JJ : elles se comparent
    # directement comme du texte (l'ordre lexicographique coïncide avec
    # l'ordre chronologique), sans CAST ni extraction — plus simple, et
    # utilisable par un index. Requête défensive : la colonne date_sortie
    # n'existe pas sur les bases antérieures à la fonctionnalité cession.
    try:
        rows = conn.execute(
            "SELECT id, libelle, valeur_brute, duree_annees, date_mise_service, "
            "compte_amort, bien_id FROM composant WHERE amortissable=1 "
            "AND (date_sortie IS NULL OR date_sortie='' OR "
            "date_sortie >= ?)", (f"{annee + 1}-01-01",)
        ).fetchall()
    except sqlite3.OperationalError:
        rows = conn.execute(
            "SELECT id, libelle, valeur_brute, duree_annees, date_mise_service, "
            "compte_amort, bien_id FROM composant WHERE amortissable=1"
        ).fetchall()
    # ── La dotation est un MOUVEMENT, pas une annuité ────────────────────
    #
    # `etat()` recalcule le plan à neuf depuis la mise en service et rend
    # l'annuité théorique de l'exercice. Prendre cette annuité telle quelle
    # revient à supposer que la comptabilité suit exactement le plan — ce
    # qui cesse d'être vrai dès qu'une durée est modifiée, qu'une dotation
    # a été saisie à la main, ou qu'un historique a été repris en
    # à-nouveaux. Trois défauts en découlaient, tous du même genre :
    #
    #   - une durée ALLONGÉE faisait repartir le plan sur une annuité plus
    #     faible sans regarder ce qui était déjà en compte ;
    #   - une dotation déjà PASSÉE dans l'exercice (OD manuelle, ou
    #     amortissements repris en AN) n'empêchait pas d'en générer une
    #     seconde, qui s'y ajoutait ;
    #   - une durée RACCOURCIE épuisait le plan alors que les comptes
    #     portaient encore une VNC, et le reste sortait du programme.
    #
    # La dotation de l'exercice est donc ce qu'il faut écrire pour porter
    # le cumul RÉELLEMENT COMPTABILISÉ au cumul que le plan prévoit à la
    # fin de cet exercice — jamais au-delà de la valeur brute. Le plan
    # redevient ainsi une cible, et la comptabilité sa mesure.
    #
    # Le raisonnement se tient par COMPTE d'amortissement, et non par
    # composant : c'est le compte qui est observable. Plusieurs composants
    # peuvent le partager (les trois postes de bâtiment de la ventilation
    # indicative sont tous sur 213150 / 281315), et l'ancien code
    # renonçait alors à toute borne — c'est précisément le cas où deux
    # composants de 8 000 € pouvaient recevoir 19 600 € d'amortissements.
    groupes: dict[str, list] = {}
    for row in rows:
        groupes.setdefault(row[5], []).append(row)

    out = []
    for c_amort, membres in groupes.items():
        theo = []
        for cid, lib, vb, duree, dms, _ca, bien_id in membres:
            dot, cumul, _vnc = etat(vb, duree, dms, annee)
            theo.append({"composant_id": cid, "libelle": lib,
                         "compte_amort": c_amort, "bien_id": bien_id,
                         "valeur_brute": round(float(vb), 2),
                         "dotation_theorique": dot,
                         "cumul_theorique": min(cumul, round(float(vb), 2))})
        brut_groupe = round(sum(t["valeur_brute"] for t in theo), 2)
        vise = round(min(sum(t["cumul_theorique"] for t in theo),
                         brut_groupe), 2)
        total_theo = round(sum(t["dotation_theorique"] for t in theo), 2)
        deja = (_cumul_comptabilise(conn, c_amort, annee) if a_comptabiliser
                else cumul_ouverture(conn, c_amort, annee))
        if deja is None and ouverture_certaine([m[4] for m in membres], annee):
            deja = 0.0
        if deja is None:
            # Lecture impossible (base incomplète, compte absent) : on
            # retombe sur le plan théorique, comportement d'origine.
            total_retenu = total_theo
        else:
            # Le mouvement qui porterait le cumul en compte au cumul visé
            # par le plan, et le maximum absolu : ce qu'il reste avant la
            # valeur brute. Ce second plafond n'a pas d'exception — un
            # actif ne s'amortit jamais au-delà de ce qu'il a coûté.
            cible = round(max(0.0, vise - deja), 2)
            plafond = round(max(0.0, brut_groupe - deja), 2)
            # SEUIL DE MATÉRIALITÉ. Suivre la cible en toute circonstance
            # ferait absorber par la dotation de l'année le moindre écart
            # d'arrondi hérité d'un historique repris — quelques euros sur
            # un cumul de cent mille, qui relèvent du constat, pas de la
            # correction automatique. En deçà du seuil, le plan fait donc
            # foi ; au-delà, c'est la comptabilité. Le seuil est celui
            # déjà retenu ailleurs dans le logiciel pour la matérialité
            # d'un écart d'amortissement : 1 € ou 1 % de la valeur brute.
            # Les écarts tolérés ici restent signalés par les contrôles
            # AMORT_ANTERIEURS et DOTATION_PLAN.
            seuil = max(1.0, 0.01 * brut_groupe)
            if abs(cible - total_theo) <= seuil:
                total_retenu = total_theo
            else:
                # JAMAIS AU-DELÀ DE L'ANNUITÉ DU PLAN. La dotation peut être
                # réduite par la comptabilité, jamais augmentée par elle :
                # rattraper d'office un cumul en retard reviendrait à
                # déduire l'année N un amortissement qui aurait dû l'être
                # en N-1, alors que l'article 39 B du CGI le tient pour
                # IRRÉGULIÈREMENT DIFFÉRÉ, donc définitivement perdu. Un
                # retard se constate et se traite ; il ne se rattrape pas
                # tout seul. C'est l'objet du contrôle `AMORT_CUMUL`.
                total_retenu = min(total_theo, cible)
            total_retenu = round(min(total_retenu, plafond), 2)

        if abs(total_retenu - total_theo) <= 0.005:
            for t in theo:                       # le plan s'applique tel quel
                t["dotation"] = t["dotation_theorique"]
                t["cumul_fin"] = t["cumul_theorique"]
        else:
            # Répartition entre les composants du compte, au prorata de
            # leur annuité théorique — à défaut (plan épuisé pour tous),
            # au prorata de leur valeur brute. Pour un compte à composant
            # UNIQUE, le cas de très loin le plus fréquent, la répartition
            # est l'identité et les chiffres sont exacts.
            base = [t["dotation_theorique"] for t in theo]
            if sum(base) <= 0.005:
                base = [t["valeur_brute"] for t in theo]
            total_base = sum(base)
            reparti = 0.0
            for i, t in enumerate(theo):
                part = (round(total_retenu * base[i] / total_base, 2)
                        if total_base > 0 else 0.0)
                if i == len(theo) - 1:      # le dernier absorbe l'arrondi
                    part = round(total_retenu - reparti, 2)
                reparti = round(reparti + part, 2)
                t["dotation"] = part
                # Part du cumul déjà en compte imputée à ce composant :
                # une ESTIMATION dès que le compte est partagé, exacte
                # sinon. Elle ne sert qu'à la trace du plan (2033-C).
                quote = (t["cumul_theorique"] / vise if vise > 0
                         else t["valeur_brute"] / brut_groupe
                         if brut_groupe > 0 else 0.0)
                t["cumul_fin"] = round(min((deja or 0.0) * quote + part,
                                           t["valeur_brute"]), 2)
        for t in theo:
            if t["dotation"] > 0.005:
                t["vnc_fin"] = round(t["valeur_brute"] - t["cumul_fin"], 2)
                out.append(t)
    return out


def cumul_ouverture(conn: sqlite3.Connection, compte_amort: str | None,
                    annee: int) -> float | None:
    """Cumul d'amortissement en compte à l'OUVERTURE de `annee`, c'est-à-dire
    avant toute dotation de cet exercice.

    Distinct de `_cumul_comptabilise`, qui rend le cumul tel qu'il se
    présente AU MOMENT de clôturer — lequel inclut la dotation de l'année
    dès qu'elle est passée. Les contrôles qui comparent l'historique au
    plan ont besoin du premier ; le moteur de dotation, du second.

    Ce sont les à-nouveaux de l'exercice qui portent cette ouverture. À
    défaut d'à-nouveaux, on lit la clôture du dernier exercice clos.
    """
    if not compte_amort:
        return None
    try:
        r = conn.execute(
            "SELECT ROUND(SUM(l.credit - l.debit), 2) FROM ligne l "
            "JOIN ecriture e ON e.id = l.ecriture_id "
            "WHERE l.compte_num = ? AND e.exercice_annee = ? "
            "AND e.journal_code = 'AN'", (compte_amort, annee)).fetchone()
        if r is not None and r[0] is not None:
            return float(r[0])
        prec = _dernier_exercice_clos(conn, annee)
        if prec is None:
            return None            # ouverture inconnue : voir ci-dessous
        r = conn.execute(
            "SELECT COALESCE(ROUND(SUM(l.credit - l.debit), 2), 0) FROM ligne l "
            "JOIN ecriture e ON e.id = l.ecriture_id "
            "WHERE l.compte_num = ? AND e.exercice_annee = ?",
            (compte_amort, prec)).fetchone()
        return float(r[0]) if r else 0.0
    except sqlite3.Error:
        return None


def ouverture_certaine(dates_mise_service, annee: int) -> bool:
    """Vrai si l'ouverture de `annee` ne peut RIEN porter pour ces
    composants : tous sont mis en service pendant l'exercice ou après.

    Sans cela, un premier exercice sans historique antérieur en base est
    tenu pour « historique inconnu », et toute comparaison au plan est
    abandonnée — y compris quand il n'y a rien à connaître, l'actif
    n'existant pas avant. C'est ce qui faisait taire le contrôle du
    minimum d'amortissement sur une clôture sans dotation.
    """
    annees = [int(str(d)[:4]) for d in dates_mise_service if d]
    return bool(annees) and min(annees) >= annee


def _dernier_exercice_clos(conn: sqlite3.Connection, annee: int) -> int | None:
    return conn.execute(
        "SELECT MAX(e.exercice_annee) FROM ecriture e "
        "JOIN exercice x ON x.annee = e.exercice_annee "
        "WHERE e.exercice_annee < ? AND x.statut = 'clos'",
        (annee,)).fetchone()[0]


def _cumul_comptabilise(conn: sqlite3.Connection, compte_amort: str | None,
                        annee: int) -> float | None:
    """Cumul d'amortissement RÉELLEMENT écrit sur le compte, tel qu'il se
    présente au moment de clôturer `annee`.

    Renvoie None quand la lecture n'est pas possible (base incomplète) :
    on retombe alors sur le plan théorique, comportement d'origine.

    Deux pièges de lecture, dans ce schéma :

    1. Ne PAS additionner tous les exercices. Les à-nouveaux de chaque
       année reportent déjà le solde de la précédente : la somme
       doublerait le cumul.
    2. Lire l'exercice COURANT, et non le dernier exercice clos, dès qu'il
       est mouvementé. C'est là que se trouvent les amortissements repris
       en à-nouveaux — y compris sur un tout premier exercice, où il
       n'existe aucun antérieur — et les dotations déjà saisies à la main.
       Les ignorer, c'était en générer une seconde par-dessus.

    L'exercice courant fait donc foi lorsque le compte y est mouvementé,
    ce qui suppose l'exercice ouvert avec ses à-nouveaux — ce que le
    contrôle `AN_ABSENTS` vérifie par ailleurs. À défaut, on se rabat sur
    le dernier exercice clos antérieur.

    ET SURTOUT : « rien n'a été comptabilisé » n'est pas « on ne sait
    pas ». Sans aucun exercice clos antérieur ni mouvement sur le compte,
    la base ne CONTIENT simplement pas l'historique — un dossier repris à
    partir de 2026 pour un bien mis en service en 2020. Rendre 0 dans ce
    cas ferait conclure à six années d'amortissement omises, et le moteur
    les rattraperait toutes d'un coup. On rend donc None : aucune borne,
    le plan s'applique tel quel, comme avant.
    """
    if not compte_amort:
        return None
    try:
        def solde(an: int) -> float | None:
            r = conn.execute(
                "SELECT ROUND(SUM(l.credit - l.debit), 2) FROM ligne l "
                "JOIN ecriture e ON e.id = l.ecriture_id "
                "WHERE l.compte_num = ? AND e.exercice_annee = ?",
                (compte_amort, an)).fetchone()
            return None if r is None or r[0] is None else float(r[0])

        courant = solde(annee)
        if courant is not None:
            return courant
        prec = _dernier_exercice_clos(conn, annee)
        return None if prec is None else (solde(prec) or 0.0)
    except sqlite3.Error:
        return None


# ── Ventilation initiale d'un bien ─────────────────────────────────────────
# Un prix d'acquisition n'est pas une masse unique : chaque composante se
# déprécie à son rythme, et c'est cette décomposition qui fait tout
# l'intérêt fiscal du réel. Faute de la proposer, le logiciel laissait
# l'utilisateur créer des composants au fil de l'eau, sans garantie que
# leur somme corresponde au prix payé (constat d'usage).
#
# Les PARTS ci-dessous sont des ordres de grandeur usuels, à ajuster : la
# répartition doit refléter la réalité du bien et les pièces de
# l'acquisition. Les DURÉES suivent les usages admis par l'administration
# (BOI-ANNX-000115), qui restent eux aussi indicatifs.
VENTILATION_INDICATIVE = [
    {"cle": "terrain", "libelle": "Terrain", "categorie": "Terrain",
     "part": 0.15, "duree": 0, "compte_immo": "211550",
     "note": "Jamais amortissable. Sa quote-part figure souvent dans "
             "l'acte ou peut s'estimer d'après les valeurs foncières "
             "locales."},
    {"cle": "gros_oeuvre", "libelle": "Gros œuvre / structure",
     "categorie": "Bâtiment", "part": 0.45, "duree": 50,
     "compte_immo": "213150",
     "note": "Murs, planchers, charpente : la part la plus longue à "
             "amortir."},
    {"cle": "facade", "libelle": "Façade / étanchéité / toiture",
     "categorie": "Bâtiment", "part": 0.10, "duree": 25,
     "compte_immo": "213150",
     "note": "Enveloppe du bâtiment, renouvelée plus souvent que la "
             "structure."},
    {"cle": "installations", "libelle": "Installations techniques",
     "categorie": "Bâtiment", "part": 0.15, "duree": 20,
     "compte_immo": "213150",
     "note": "Chauffage, électricité, plomberie, ventilation."},
    {"cle": "agencements", "libelle": "Agencements intérieurs",
     "categorie": "Agencement", "part": 0.10, "duree": 15,
     "compte_immo": "218100",
     "note": "Cloisons, revêtements, cuisine intégrée, salle de bains."},
    {"cle": "mobilier", "libelle": "Mobilier et électroménager",
     "categorie": "Mobilier", "part": 0.05, "duree": 8,
     "compte_immo": "218400",
     "note": "Ce qui fait le « meublé ». Durée courte : 5 à 10 ans selon "
             "la nature. À isoler du bâti, sans quoi il s'amortit sur "
             "des décennies au lieu de quelques années."},
]


def normaliser_quote_part(valeur, prix_total: float | None = None):
    """
    Interprète une quote-part de terrain saisie librement.

    Le champ attend une FRACTION (0,09 pour 9 %). Trois saisies plausibles
    étaient jusqu'ici ignorées SANS UN MOT — la ventilation retombait alors
    sur sa part indicative de 15 %, ce qui fausse l'amortissement puisque
    le terrain n'est pas amortissable :
      - un pourcentage (9 ou 7,35) ;
      - un montant en euros (8 600) ;
      - la valeur 1, refusée par la borne stricte.
    On les reconnaît désormais, plutôt que de deviner en silence.

    Renvoie (fraction, mention) — mention non vide si la saisie a été
    réinterprétée, pour pouvoir le DIRE à l'utilisateur.
    """
    if valeur in (None, ""):
        return None, ""
    try:
        v = float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        return None, ""
    if v < 0:
        return None, ""
    if v == 0:
        # Zéro n'est pas « rien ». Renseigner 0 est une AFFIRMATION — le
        # bien ne comporte pas de quote-part de terrain — et elle était
        # traitée comme une absence de saisie : la proposition retombait
        # sur sa part indicative de 15 %, soit 15 000 € sortis de la base
        # amortissable sur un prix de 100 000 €, en contradiction avec ce
        # qui venait d'être saisi.
        return 0.0, ""
    if 0 < v <= 1:
        return v, ""
    if v <= 100:
        return v / 100, (f"quote-part lue comme {v:g} %, soit "
                         f"{v / 100:.4f}".rstrip("0").rstrip(".") + ")")
    if prix_total and 0 < v < prix_total:
        return v / prix_total, (f"quote-part lue comme un montant de "
                                f"{v:,.2f} €".replace(",", " ") + ")")
    return None, ""


def ventilation_proposee(prix_total: float,
                         quote_part_terrain: float | None = None) -> list[dict]:
    """Pré-remplit la ventilation à partir du prix payé.

    Si la quote-part de terrain est connue (elle figure souvent dans
    l'acte), elle prime sur la part indicative et le reste se répartit
    proportionnellement sur les autres postes : mieux vaut une donnée
    réelle qu'une moyenne.
    """
    lignes = [dict(x) for x in VENTILATION_INDICATIVE]
    quote_part_terrain, _mention = normaliser_quote_part(quote_part_terrain,
                                                         prix_total)
    # Borne HAUTE incluse : une quote-part de 1 (terrain nu) était rejetée
    # par une comparaison stricte et retombait sur la part indicative.
    fournie = (quote_part_terrain is not None
               and 0 <= quote_part_terrain <= 1)
    if fournie:
        reste = 1 - quote_part_terrain
        # `reste` vaut 1 quand la quote-part est nulle : tout le prix se
        # répartit alors sur les postes amortissables.
        autres = sum(x["part"] for x in lignes if x["cle"] != "terrain")
        for x in lignes:
            x["part"] = (quote_part_terrain if x["cle"] == "terrain"
                         else x["part"] / autres * reste if autres else 0.0)
    for x in lignes:
        x["montant"] = round(prix_total * x["part"], 2)
    # L'arrondi ne doit pas faire perdre ou inventer des euros — mais il ne
    # doit pas non plus déplacer la QUOTE-PART FOURNIE PAR L'UTILISATEUR.
    #
    # Deux défauts se combinaient. Les proportions des autres postes étaient
    # arrondies à quatre décimales avant d'être appliquées au prix : sur
    # 100 000 €, cela suffit à créer un écart de plusieurs euros. Puis cet
    # écart était absorbé par la ligne au plus gros montant — le terrain,
    # justement, quand sa quote-part est élevée. Résultat : 13 € ajoutés au
    # terrain NON AMORTISSABLE, contre la quote-part lue dans l'acte, et
    # autant de potentiel amortissable en moins.
    #
    # Les proportions ne sont donc plus arrondies (seuls les montants le
    # sont), et le centime résiduel est absorbé par le plus gros poste
    # AMORTISSABLE : la donnée réelle prime sur la clé de répartition, qui
    # n'est qu'indicative.
    ecart = round(prix_total - sum(x["montant"] for x in lignes), 2)
    if ecart:
        absorbables = [x for x in lignes
                       if not (fournie and x["cle"] == "terrain")]
        cible = max(absorbables or lignes, key=lambda x: x["montant"])
        cible["montant"] = round(cible["montant"] + ecart, 2)
    return lignes


def generer_cloture(conn: sqlite3.Connection, annee: int, date_cloture: str | None = None,
                    commit: bool = True) -> dict:
    """
    Crée l'écriture OD de dotation au 31/12 (681120 / 281xxx par composant).

    Garde-fou : refuse si une dotation existe déjà pour l'exercice (une
    seconde écriture DAA doublerait la charge d'amortissement).
    `commit=False` : laisse la transaction ouverte (clôture atomique).
    """
    # Le verrou anti-doublon regarde l'EFFET COMPTABLE, pas la seule
    # présence de la pièce. Une DAA proprement contre-passée laisse son
    # écriture d'origine en place pour un effet net nul : le verrou
    # bloquait alors définitivement toute reprise, sans dire pourquoi, et
    # l'exercice se clôturait sans aucun amortissement. La pièce existe,
    # l'amortissement non — ce sont deux choses.
    deja = conn.execute(
        "SELECT ecriture_num FROM ecriture WHERE exercice_annee=? "
        "AND journal_code='OD' AND piece_ref='DAA'", (annee,)).fetchone()
    if deja is not None:
        net = conn.execute(
            "SELECT ROUND(COALESCE(SUM(l.debit - l.credit),0),2) FROM ligne l "
            "JOIN ecriture e ON e.id = l.ecriture_id "
            "WHERE e.exercice_annee=? AND l.compte_num=? "
            "AND COALESCE(l.libelle,'') NOT LIKE 'DAA cession%'",
            (annee, CONTREPARTIE_DOTATION)).fetchone()[0]
        if net > 0.005:
            raise ValueError(f"Dotation aux amortissements déjà générée pour "
                             f"{annee} (écriture OD n°{deja[0]}).")
    date_cloture = date_cloture or f"{annee}-12-31"
    # Vue « ce qu'il RESTE à écrire » : une dotation déjà passée dans
    # l'exercice — OD manuelle, ou amortissements repris en à-nouveaux sur
    # un premier exercice — était ignorée, et la génération en ajoutait une
    # seconde par-dessus. Sur un composant d'un an déjà doté de 12 000 €,
    # le compte d'amortissement finissait à 24 000 € pour 12 000 € de brut.
    dotations = dotations_exercice(conn, annee, a_comptabiliser=True)
    if not dotations:
        return {"ecriture_id": None, "total": 0.0, "nb_composants": 0}

    # Garde-fou : un composant amortissable sans compte d'amortissement
    # produisait une ligne à compte NULL, donc une IntegrityError SQLite
    # illisible en pleine clôture. On nomme le coupable et le geste.
    # Le compte d'amortissement doit être CELUI DU PLAN pour le compte
    # d'immobilisation du composant. Sa seule présence était tenue pour
    # suffisante : un terrain portant par erreur un compte de mobilier
    # recevait une dotation en bonne et due forme, et rien ne la
    # contredisait — ni le contrôle, ni la clôture.
    incoherents = []
    for d in dotations:
        c_immo = conn.execute("SELECT compte_immo FROM composant WHERE id=?",
                              (d["composant_id"],)).fetchone()
        immo = c_immo[0] if c_immo else ""
        attendu = plan_immo.compte_amortissement(immo)
        if not plan_immo.amortissement_coherent(immo, d["compte_amort"]):
            incoherents.append(
                f"« {d['libelle']} » (immobilisation {c_immo[0] if c_immo else '?'}"
                f" → amortissement {d['compte_amort']}, attendu "
                f"{attendu or 'aucun : ce compte ne s’amortit pas'})")
    if incoherents:
        raise ValueError(
            "Clôture impossible : le compte d'amortissement ne correspond "
            "pas au compte d'immobilisation pour " + ", ".join(incoherents)
            + ". La dotation irait sur un poste étranger au bien. Corrigez "
              "ces composants dans la page Immobilisations.")

    orphelins = [d["libelle"] for d in dotations if not d["compte_amort"]]
    if orphelins:
        raise ValueError(
            "Clôture impossible : le(s) composant(s) "
            + ", ".join(f"« {x} »" for x in orphelins)
            + " ont une durée d'amortissement mais aucun compte "
              "d'amortissement — c'est le cas d'un terrain, qui ne "
              "s'amortit pas. Corrigez-les dans la page Immobilisations "
              "(durée à 0), puis relancez la clôture.")

    libelles_bien = dict(conn.execute("SELECT id, libelle FROM bien").fetchall())
    lignes: list[tuple] = []
    total_check = 0.0
    for d in dotations:
        bien_lib = libelles_bien.get(d["bien_id"], "")
        lib = f"DAA - {d['libelle']} - {bien_lib}"
        lignes.append((CONTREPARTIE_DOTATION, d["dotation"], 0.0, lib))
        lignes.append((d["compte_amort"], 0.0, d["dotation"], lib))
        total_check += d["dotation"]
    r = ecritures.inserer(conn, journal="OD", date=date_cloture, annee=annee,
                          piece_ref="DAA", libelle="Dotation aux amortissements",
                          lignes=lignes, commit=False)
    eid, num = r["ecriture_id"], r["ecriture_num"]
    cur = conn.cursor()

    total = 0.0
    for d in dotations:
        # Trace du plan (pour audit et futur tableau 2033-C).
        cur.execute(
            "INSERT OR REPLACE INTO plan_amortissement "
            "(composant_id, exercice_annee, dotation, cumul_fin, vnc_fin) VALUES (?,?,?,?,?)",
            (d["composant_id"], annee, d["dotation"], d["cumul_fin"], d["vnc_fin"]))
        total += d["dotation"]

    if commit:
        conn.commit()
    return {"ecriture_id": eid, "ecriture_num": num, "total": round(total, 2),
            "nb_composants": len(dotations)}
