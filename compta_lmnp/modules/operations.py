# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Jalon J2 — Saisie par opérations métier.

On ne saisit pas un débit/crédit, on saisit un FAIT (« loyer de mars, 795 € »).
Le gabarit génère automatiquement l'écriture en partie double équilibrée :
la contrepartie est toujours le compte 108000 (Exploitant).
"""
from __future__ import annotations

import calendar
import math
import sqlite3
from datetime import date

import ecritures
from gabarits import COMPTE_CONTREPARTIE, gabarit


def saisir(conn: sqlite3.Connection, *, type: str, montant: float, date_operation: str,
           periode: str | None = None, bien_id: int = 1, tiers: str = "",
           libelle: str | None = None, exercice: int | None = None,
           piece_ref: str | None = None, source: str = "saisie",
           commit: bool = True) -> dict:
    """Crée une opération + son écriture équilibrée. Renvoie {operation_id, ecriture_id}.

    `commit=False` laisse la transaction OUVERTE, pour qu'un appelant puisse
    enchaîner plusieurs saisies et les valider — ou les annuler — en bloc.
    C'est ce que la validation d'un import bancaire réclamait : elle bouclait
    sur cette fonction, qui committait à chaque tour, si bien qu'un échec à
    la septième ligne sur dix laissait les six premières en base, sans retour
    arrière ni indication de l'endroit où l'import s'était arrêté.

    Le défaut par défaut reste `True` : tous les autres appelants — le
    guichet de saisie, la duplication, les tests — attendent une opération
    durable au retour.
    """
    g = gabarit(type, conn)
    if bien_id is not None and not conn.execute(
            "SELECT 1 FROM bien WHERE id=?", (bien_id,)).fetchone():
        raise ValueError(
            "Aucun bien enregistré : créez d'abord votre logement dans la "
            "page Immobilisations (le temps d'une minute), puis revenez "
            "saisir — chaque opération se rattache à un bien.")
    montant = float(montant)
    # isfinite AVANT les comparaisons : NaN les traverse toutes (nan <= 0 est
    # faux) et aurait fini dans une écriture — donc dans le FEC.
    if not math.isfinite(montant):
        raise ValueError(f"Montant invalide : {montant!r}.")
    montant = round(montant, 2)
    if montant <= 0:
        # Les montants restent STRICTEMENT positifs partout : c'est cette
        # règle qui protège des saisies inversées, et la contrainte de
        # schéma la fait respecter. Une opération de sens contraire ne se
        # saisit donc pas avec un signe moins, mais en choisissant la
        # NATURE correspondante — « Restitution de charges au locataire »
        # pour une régularisation en sa faveur (signalé en revue du
        # catalogue : le cas était simplement impossible à enregistrer).
        raise ValueError(
            "Le montant doit être strictement positif. Pour une "
            "régularisation en faveur du locataire, choisissez la nature "
            "« Restitution de charges au locataire ». Pour annuler une "
            "opération, utilisez le bouton « Annuler ».")
    try:
        date_op = date.fromisoformat(date_operation)
    except (TypeError, ValueError):
        raise ValueError(f"Date d'opération invalide : {date_operation!r} "
                         "(format attendu AAAA-MM-JJ).") from None
    annee = exercice if exercice is not None else date_op.year
    lib = libelle or g["libelle"]

    # --- Écriture : contrepartie 108000, compte du gabarit selon la nature ---
    if g["nature"] == "produit":          # encaissement : 108000 D / produit C
        lignes = [(COMPTE_CONTREPARTIE, montant, 0.0), (g["compte"], 0.0, montant)]
    else:                                  # charge : charge D / 108000 C
        lignes = [(g["compte"], montant, 0.0), (COMPTE_CONTREPARTIE, 0.0, montant)]

    r = ecritures.inserer(conn, journal="BQ", date=date_operation, annee=annee,
                          libelle=lib, lignes=lignes,
                          piece_ref=piece_ref or periode or "NA", commit=False)
    eid, num = r["ecriture_id"], r["ecriture_num"]

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO operation (exercice_annee, type, bien_id, tiers, periode, "
        "date_operation, montant, libelle, ecriture_id, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (annee, type, bien_id, tiers, periode, date_operation, montant, lib, eid, source),
    )
    oid = cur.lastrowid
    if commit:
        conn.commit()
    return {"operation_id": oid, "ecriture_id": eid, "ecriture_num": num,
            "montant": montant}


def saisir_ventilee(conn: sqlite3.Connection, *, parts: list[dict],
                    date_operation: str, bien_id: int | None, libelle: str,
                    exercice: int | None = None, piece_ref: str | None = None,
                    source: str = "saisie") -> dict:
    """UN paiement ventilé sur plusieurs charges : une seule écriture, une
    ligne de débit par part et une seule contrepartie 108000, et une
    opération par part, toutes rattachées à cette écriture.

    C'est la forme d'une échéance d'emprunt : un prélèvement, deux charges
    de nature fiscale différente (intérêts en 661100, ligne 294 du 2033-B ;
    assurance emprunteur en 616110). Une opération par part garde visibles
    les contrôles qui raisonnent par type (intérêts absents, intérêts mal
    classés) ; une seule écriture garde la pièce entière.

    Charges uniquement (nature « charge ») ; chaque montant strictement
    positif, au centime. Ne committe jamais : l'appelant tient la
    transaction (génération en lot, tout ou rien).
    Renvoie {'operation_ids', 'ecriture_id', 'ecriture_num', 'total'}.
    """
    if not parts:
        raise ValueError("Paiement ventilé sans aucune part.")
    if bien_id is not None and not conn.execute(
            "SELECT 1 FROM bien WHERE id=?", (bien_id,)).fetchone():
        raise ValueError(f"Bien {bien_id} inconnu.")
    try:
        date_op = date.fromisoformat(date_operation)
    except (TypeError, ValueError):
        raise ValueError(f"Date d'opération invalide : {date_operation!r} "
                         "(format attendu AAAA-MM-JJ).") from None
    annee = exercice if exercice is not None else date_op.year
    lignes, preparees = [], []
    for part in parts:
        g = gabarit(part["type"], conn)
        if g["nature"] != "charge":
            raise ValueError(f"« {g['libelle']} » n'est pas une charge : un "
                             "paiement ventilé ne porte que des charges.")
        montant = float(part["montant"])
        if not math.isfinite(montant) or round(montant, 2) <= 0:
            raise ValueError(f"Montant invalide pour « {g['libelle']} » : "
                             f"{part['montant']!r}.")
        montant = round(montant, 2)
        lib = part.get("libelle") or g["libelle"]
        lignes.append((g["compte"], montant, 0.0, lib))
        preparees.append((part["type"], montant, lib, part.get("periode"),
                          part.get("tiers") or ""))
    total = round(sum(p[1] for p in preparees), 2)
    lignes.append((COMPTE_CONTREPARTIE, 0.0, total, libelle))
    r = ecritures.inserer(conn, journal="BQ", date=date_operation, annee=annee,
                          libelle=libelle, lignes=lignes,
                          piece_ref=piece_ref or "NA", commit=False)
    ids = []
    for type_, montant, lib, periode, tiers in preparees:
        ids.append(conn.execute(
            "INSERT INTO operation (exercice_annee, type, bien_id, tiers, "
            "periode, date_operation, montant, libelle, ecriture_id, source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (annee, type_, bien_id, tiers, periode, date_operation, montant,
             lib, r["ecriture_id"], source)).lastrowid)
    return {"operation_ids": ids, "ecriture_id": r["ecriture_id"],
            "ecriture_num": r["ecriture_num"], "total": total}


def operations_de_l_ecriture(conn: sqlite3.Connection,
                             operation_id: int) -> list[int]:
    """Toutes les opérations qui partagent l'écriture de celle-ci (elle
    comprise). Une seule, sauf pour un paiement ventilé."""
    return [r[0] for r in conn.execute(
        "SELECT o2.id FROM operation o JOIN operation o2 "
        "ON o2.ecriture_id = o.ecriture_id WHERE o.id=? ORDER BY o2.id",
        (operation_id,))] or [operation_id]


def dupliquer(conn: sqlite3.Connection, operation_id: int,
              decalage_mois: int = 1) -> dict:
    """
    Réplique une opération existante en décalant sa date de `decalage_mois`
    (défaut : mois suivant) — le geste type pour les loyers mensuels.

    Règles :
      - le jour est conservé, borné à la fin du mois cible (31/01 → 28-29/02) ;
      - la période suit la nouvelle date ;
      - un libellé personnalisé est conservé ; un libellé auto-généré
        (« Loyer hors charges locatives 2026-03 ») est régénéré avec la
        nouvelle période ;
      - l'exercice cible doit exister et être OUVERT (on ne réplique jamais
        dans un exercice clos ni inexistant) ;
      - la référence de pièce n'est pas recopiée : elle devient
        « Relevé bancaire MM », lisible par le déclarant comme par un
        contrôleur, au lieu d'une période nue (« 2026-08 ») qui ne disait
        pas de quel justificatif l'écriture provenait.
    """
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row          # isolé : ne modifie pas la connexion
    src = cur.execute("SELECT * FROM operation WHERE id=?",
                      (operation_id,)).fetchone()
    if src is None:
        raise ValueError(f"Opération {operation_id} introuvable.")
    if len(operations_de_l_ecriture(conn, operation_id)) > 1:
        # Dupliquer une part recopierait les intérêts sans l'assurance, avec
        # une date qui n'est plus celle du tableau : une échéance se
        # régénère depuis sa source, elle ne se duplique pas.
        raise ValueError("Cette opération fait partie d'un paiement ventilé "
                         "(échéance d'emprunt) : elle ne se duplique pas. "
                         "Générez l'échéance suivante depuis l'onglet "
                         "Emprunts.")

    a, m, j = (int(x) for x in src["date_operation"].split("-"))
    m += decalage_mois
    a += (m - 1) // 12
    m = (m - 1) % 12 + 1
    j = min(j, calendar.monthrange(a, m)[1])
    nouvelle_date = f"{a:04d}-{m:02d}-{j:02d}"
    nouvelle_periode = f"{a:04d}-{m:02d}" if src["periode"] else None

    ex = cur.execute("SELECT statut FROM exercice WHERE annee=?", (a,)).fetchone()
    if ex is None:
        raise ValueError(f"Impossible de dupliquer vers {nouvelle_date} : "
                         f"l'exercice {a} n'existe pas encore (menu Nouvel exercice).")
    if ex["statut"] != "ouvert":
        raise ValueError(f"Impossible de dupliquer vers {nouvelle_date} : "
                         f"l'exercice {a} est clos.")

    g = gabarit(src["type"], conn)
    lib = src["libelle"]
    if lib == g["libelle"]:
        lib = None                     # libellé par défaut du gabarit :
                                       # inutile de le recopier
    return saisir(conn, type=src["type"], montant=src["montant"],
                  date_operation=nouvelle_date, periode=nouvelle_periode,
                  bien_id=src["bien_id"], tiers=src["tiers"] or "",
                  libelle=lib, exercice=a, source="duplication",
                  piece_ref=f"Relevé bancaire {m:02d}")


# Seuil de MATÉRIALITÉ des écarts d'amortissement, en valeur ET en
# proportion. Un bilan d'ouverture repris d'un ancien prestataire diffère
# toujours de quelques euros du plan recalculé ici (arrondis par composant,
# conventions de prorata) : c'est du bruit. Une reprise réellement oubliée
# laisse un écart de l'ordre de 100 % du cumul attendu.
# Ce seuil est PARTAGÉ par le contrôle pré-clôture et par le contrôle de
# cohérence de la liasse : deux contrôles portant sur le même écart ne
# peuvent pas être en désaccord sur ce qui mérite une alerte.
SEUIL_MATERIALITE_EUROS = 5.00
SEUIL_MATERIALITE_RATIO = 0.01

# Référence de pièce de l'écriture de reprise des amortissements antérieurs.
# Elle sert à la RECONNAÎTRE : c'est le seul à-nouveau que ce module passe
# lui-même, et il ne doit pas être pris pour un à-nouveau de reprise de
# bilan (cf. amortissements_anterieurs_manquants).
PIECE_REPRISE_AMORT = "AN-AMORT"


def ecart_materiel(ecart: float, reference: float) -> bool:
    """L'écart mérite-t-il d'être signalé, ou n'est-ce que de l'arrondi ?"""
    return (abs(ecart) >= SEUIL_MATERIALITE_EUROS
            and abs(ecart) >= SEUIL_MATERIALITE_RATIO * abs(reference))


def amortissements_anterieurs_manquants(conn: sqlite3.Connection,
                                        annee: int) -> dict:
    """
    Écart entre les amortissements DÉJÀ COURUS au 1er janvier de l'exercice
    (plan d'amortissement, calculé depuis la mise en service) et ceux
    réellement COMPTABILISÉS sur les comptes 28.

    Le cas type : un bien acquis il y a plusieurs années, saisi dans le
    logiciel pour la première fois. L'écriture d'entrée porte la valeur
    BRUTE ; si le cumul d'amortissement antérieur n'est pas repris en
    même temps, le bilan affiche un bien neuf alors que le tableau
    2033-C, lui, calcule le plan depuis l'origine. D'où un écart qui ne
    se résorbe jamais tout seul.

    Renvoie {'total': écart, 'par_compte': {compte: montant}, 'detail': [...]}.
    """
    import amortissement
    attendu: dict[str, float] = {}
    detail = []
    for lib, vb, duree, dms, cpt, amortissable in conn.execute(
            "SELECT libelle, valeur_brute, duree_annees, date_mise_service, "
            "compte_amort, amortissable FROM composant"):
        if not (amortissable and duree and dms and cpt):
            continue
        if int(dms[:4]) >= annee:
            continue                       # entré pendant l'exercice : normal
        _, cumul_ouverture, _ = amortissement.etat(vb, duree, dms, annee - 1)
        if cumul_ouverture <= 0:
            continue
        attendu[cpt] = round(attendu.get(cpt, 0.0) + cumul_ouverture, 2)
        detail.append({"composant": lib, "compte": cpt,
                       "cumul_ouverture": round(cumul_ouverture, 2)})
    par_compte, total = {}, 0.0
    for cpt, montant in attendu.items():
        # Ce qui est DÉJÀ comptabilisé à l'ouverture de l'exercice.
        #
        # Deux situations, et il ne faut pas les additionner : si
        # l'exercice a des À-NOUVEAUX (journal AN), ils portent À EUX
        # SEULS toute la situation d'ouverture — c'est leur rôle. Les
        # exercices antérieurs éventuellement présents en base sont alors
        # déjà résumés dedans, et les compter en plus reviendrait à
        # doubler le cumul (constaté en préparant le dossier de
        # démonstration, qui contient désormais l'exercice précédent
        # complet ET ses à-nouveaux).
        #
        # Sans à-nouveaux, on retombe sur le cumul des exercices
        # antérieurs — cas d'un dossier tenu ici depuis l'origine.
        #
        # Les à-nouveaux que NOUS avons passés (PIECE_REPRISE_AMORT) ne
        # comptent pas comme des à-nouveaux « porteurs de la situation
        # d'ouverture » : ils la COMPLÈTENT. Les confondre inversait la
        # portée au deuxième appel — un dossier tenu ici depuis l'origine,
        # sans à-nouveaux, passait après la première reprise du cumul des
        # exercices antérieurs au seul montant repris, et redemandait donc
        # la différence : le cumul du 28 finissait à 10 438 € pour un plan
        # de 8 438 €, sans qu'aucun équilibre ne le trahisse.
        a_des_an = conn.execute(
            "SELECT 1 FROM ecriture WHERE exercice_annee=? "
            "AND journal_code='AN' AND piece_ref <> ? LIMIT 1",
            (annee, PIECE_REPRISE_AMORT)).fetchone() is not None
        portee = ("e.exercice_annee = ? AND e.journal_code = 'AN'"
                  if a_des_an else
                  "e.exercice_annee < ? OR (e.exercice_annee = ? AND "
                  "e.journal_code = 'AN' AND e.piece_ref = ?)")
        args = ((cpt, annee) if a_des_an
                else (cpt, annee, annee, PIECE_REPRISE_AMORT))
        comptabilise = conn.execute(
            "SELECT COALESCE(ROUND(SUM(l.credit - l.debit), 2), 0) FROM ligne l "
            "JOIN ecriture e ON e.id = l.ecriture_id "
            f"WHERE l.compte_num = ? AND ({portee})",
            args).fetchone()[0]
        ecart = round(montant - comptabilise, 2)
        if ecart_materiel(ecart, montant):
            par_compte[cpt] = ecart
            total = round(total + ecart, 2)
    return {"total": total, "par_compte": par_compte, "detail": detail}


def reprendre_amortissements_anterieurs(conn: sqlite3.Connection, annee: int,
                                        commit: bool = True) -> dict:
    """
    Comptabilise le « à-nouveau » d'amortissement : une écriture OD au
    premier jour de l'exercice qui porte au crédit des comptes 28 le
    cumul déjà couru avant l'entrée du bien dans le logiciel, par le
    débit du compte de l'exploitant (108000).

    Le résultat de l'exercice n'est PAS touché : ce n'est pas une
    dotation de l'année, c'est la reconstitution d'une situation
    antérieure. Seul le bilan change — il cesse de présenter comme neuf
    un bien amorti depuis des années.

    L'écart se reprend DANS LES DEUX SENS. Le cas courant le crédite : les
    comptes 28 portent moins que le plan. Mais l'inverse existe, et il
    n'était pas prévu — les comptes portent PLUS que le plan :
      - les à-nouveaux repris d'un cabinet appliquaient d'autres durées
        que celles saisies ici (un mobilier amorti en 5 ans chez lui,
        déclaré sur 8 ans ici) ;
      - une durée corrigée après une première reprise, ou un composant
        supprimé et resaisi, réduit le cumul attendu.
    L'écart devenait alors négatif et partait tel quel au crédit : la base
    le rejetait par « CHECK constraint failed: debit >= 0 AND credit >= 0 »
    — un message de moteur, sur une opération légitime, et la reprise
    restait impossible à rejouer. Un excédent d'amortissement se corrige
    au DÉBIT du compte 28, c'est tout ce qui manquait.
    """
    manquants = amortissements_anterieurs_manquants(conn, annee)
    if not manquants["par_compte"]:
        raise ValueError("Aucun amortissement antérieur à reprendre : le "
                         "bilan est déjà cohérent avec le plan.")
    statut = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                          (annee,)).fetchone()
    if statut is None:
        raise ValueError(f"L'exercice {annee} n'existe pas.")
    if statut[0] != "ouvert":
        raise ValueError(f"L'exercice {annee} est clos : la reprise doit "
                         "être passée sur un exercice ouvert.")
    lignes = [(cpt, 0.0, montant, "Amortissements antérieurs - reprise")
              if montant >= 0 else
              (cpt, -montant, 0.0, "Amortissements antérieurs - excédent repris")
              for cpt, montant in sorted(manquants["par_compte"].items())]
    total = manquants["total"]
    # Contrepartie exploitant du SOLDE. Un total nul avec des écarts de
    # sens opposés s'équilibre entre comptes 28 : pas de ligne à 0,00 €,
    # que le FEC afficherait sans rien dire.
    if total > 0:
        lignes.append(("108000", total, 0.0,
                       "Amortissements antérieurs - contrepartie exploitant"))
    elif total < 0:
        lignes.append(("108000", 0.0, -total,
                       "Amortissements antérieurs - contrepartie exploitant"))
    res = ecritures.inserer(
        conn, journal="AN", annee=annee, date=f"{annee}-01-01",
        libelle="Reprise des amortissements antérieurs à l'entrée en gestion",
        piece_ref=PIECE_REPRISE_AMORT, lignes=lignes, commit=commit)
    return {"total": total, "par_compte": manquants["par_compte"],
            "ecriture_num": res["ecriture_num"]}


def saisir_appel_charges(conn: sqlite3.Connection, *, date_operation: str,
                         periode: str | None = None,
                         charges_courantes: float = 0.0,
                         fonds_alur: float = 0.0,
                         travaux: float = 0.0,
                         bien_id: int = 1, tiers: str = "",
                         exercice: int | None = None) -> dict:
    """
    Ventile UN appel de charges du syndic en ses composantes fiscales,
    rattachées par une même référence de pièce (APPEL AAAA-MM) :

      - charges_courantes → 614100 « Charges locatives et de copropriété »,
        DÉDUCTIBLE en totalité (y compris la quote-part récupérable sur le
        locataire : en BIC les provisions encaissées sont imposées en
        produits, la déduction est donc symétrique — conventions des offres payantes) ;
      - fonds_alur → 614100 « Fonds travaux ALUR », comptabilisé en charge
        mais RÉINTÉGRÉ fiscalement à la clôture (contribution capitalisée,
        art. 14-2 loi de 1965 — non déductible) ;
      - travaux → 615200 « Entretien et réparations » pour les appels
        travaux hors budget ; si ce sont de GROS travaux (ravalement,
        toiture…), préférez une immobilisation (menu Immobilisations).

    Renvoie {'operations': [...], 'total': montant total de l'appel}.
    """
    parts = [("charge_copro", charges_courantes,
              "Appel de charges - budget courant"),
             ("fonds_travaux_alur", fonds_alur,
              "Appel de charges - fonds travaux ALUR"),
             ("maintenance", travaux,
              "Appel de charges - travaux hors budget")]
    parts = [(t, round(float(m), 2), lib) for t, m, lib in parts
             if round(float(m), 2) > 0]
    if not parts:
        raise ValueError("Appel de charges vide : renseignez au moins un montant.")
    per = periode or date_operation[:7]
    ref = f"APPEL {per}"
    # TOUT OU RIEN. Chaque composante était saisie avec le commit par
    # défaut : un montant invalide sur la troisième laissait les deux
    # premières en base — 700 € de charges comptables persistaient pour un
    # appel annoncé en erreur, et une relance complète les aurait doublées.
    # Un appel de charges se ventile, il ne se fractionne pas : les trois
    # composantes portent la même référence de pièce et décrivent un seul
    # document du syndic.
    deja_en_transaction = conn.in_transaction
    try:
        ops = [saisir(conn, type=t, montant=m, date_operation=date_operation,
                      periode=per, bien_id=bien_id, tiers=tiers, libelle=lib,
                      exercice=exercice, piece_ref=ref, commit=False)
               for t, m, lib in parts]
        if not deja_en_transaction:
            conn.commit()
    except Exception:
        if not deja_en_transaction:
            conn.rollback()
        raise
    return {"operations": ops,
            "total": round(sum(m for _, m, _ in parts), 2),
            "piece_ref": ref}


def saisir_acquisition(conn: sqlite3.Connection, *, compte_immo: str, montant: float,
                       date_operation: str, libelle: str,
                       exercice: int | None = None,
                       commit: bool = True) -> dict:
    """
    Écriture d'acquisition d'une immobilisation : débit compte 2xx / crédit
    108000 (apport de l'exploitant, convention trésorerie des logiciels du marché). Sans elle,
    le composant n'existerait qu'en référentiel et le bilan serait faux.
    """
    montant = round(float(montant), 2)
    if montant <= 0:
        raise ValueError("Le montant doit être strictement positif.")
    annee = exercice if exercice is not None else int(date_operation[:4])
    lib = f"Acquisition - {libelle}"
    # `commit=False` permet à un appelant d'enchaîner PLUSIEURS acquisitions
    # dans une seule transaction — la ventilation d'un bien en composants,
    # par exemple, doit être tout-ou-rien : un échec sur la 3e ligne ne doit
    # pas laisser les deux premières écrites (constaté en audit).
    return ecritures.inserer(conn, journal="OD", date=date_operation, annee=annee,
                             libelle=lib, piece_ref="ACQ", commit=commit,
                             lignes=[(compte_immo, montant, 0.0),
                                     (COMPTE_CONTREPARTIE, 0.0, montant)])


def assurer_colonne_annulee(conn) -> None:
    """Colonne operation.annulee, créée à la volée (installations existantes)."""
    try:
        conn.execute("ALTER TABLE operation ADD COLUMN annulee INTEGER "
                     "NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass


def annuler(conn: sqlite3.Connection, operation_id: int,
            commit: bool = True) -> dict:
    """
    Annule une opération par CONTRE-PASSATION — le geste comptable, pas une
    suppression : une écriture validée ne disparaît jamais (la numérotation
    du FEC reste dense, la piste d'audit reste complète). Une écriture
    INVERSE est passée à la même date, libellée « Annulation », et
    l'opération d'origine est marquée `annulee` :
      - tous les calculs fondés sur les ÉCRITURES (résultat, plafond 39 C,
        liasse, FEC) se neutralisent d'eux-mêmes ;
      - les usages fondés sur les OPÉRATIONS (réintégration ALUR
        automatique, contrôles de complétude et de doublons) excluent les
        opérations marquées.
    """
    assurer_colonne_annulee(conn)
    # VERROU D'ÉCRITURE AVANT LA LECTURE DU MARQUEUR. Deux annulations
    # simultanées de la même opération lisaient toutes deux « non annulée »,
    # puis passaient chacune leur contre-passation : le loyer était
    # contre-passé DEUX fois, et les produits minorés de 800 € sans qu'aucun
    # déséquilibre ne le trahisse. Le verrou pris plus loin par l'insertion
    # sérialisait bien les écritures, mais ne faisait pas relire le marqueur
    # contrôlé avant lui — un contrôle pris hors verrou ne décrit que le
    # passé. Avec BEGIN IMMEDIATE, la seconde demande attend son tour et
    # relit un marqueur déjà positionné.
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    op = conn.execute("SELECT * FROM operation WHERE id=?",
                      (operation_id,)).fetchone()
    if op is None:
        raise ValueError(f"Opération {operation_id} inconnue.")
    op = dict(zip([c[0] for c in conn.execute(
        "SELECT * FROM operation LIMIT 0").description], op))         if not isinstance(op, sqlite3.Row) else dict(op)
    if op.get("annulee"):
        raise ValueError("Cette opération est déjà annulée.")
    statut = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                          (op["exercice_annee"],)).fetchone()
    if statut and statut[0] == "clos":
        raise ValueError(
            f"L'exercice {op['exercice_annee']} est clos : passez une "
            "régularisation sur l'exercice ouvert, ou restaurez la "
            "sauvegarde d'avant clôture (page Dossiers).")
    lignes_orig = conn.execute(
        "SELECT compte_num, debit, credit, libelle FROM ligne "
        "WHERE ecriture_id=?", (op["ecriture_id"],)).fetchall()
    if not lignes_orig:
        raise ValueError("Écriture d'origine introuvable — annulation "
                         "impossible.")
    lignes_inverses = [(r[0], round(r[2], 2), round(r[1], 2),
                        f"Annulation - {r[3] or ''}".strip(" -"))
                       for r in lignes_orig]
    res = ecritures.inserer(
        conn, journal="OD", annee=op["exercice_annee"],
        date=op["date_operation"],
        libelle=f"Annulation : {op.get('libelle') or op['type']}",
        piece_ref=f"ANNUL-{operation_id}", commit=False,
        lignes=lignes_inverses)
    # Un paiement VENTILÉ (échéance d'emprunt) porte plusieurs opérations
    # sur une écriture : la contre-passation ci-dessus les annule toutes
    # en comptabilité, elles sont donc toutes marquées. N'en marquer qu'une
    # laissait les autres « vivantes » pour les contrôles, alors que leurs
    # montants venaient d'être contre-passés.
    liees = operations_de_l_ecriture(conn, operation_id)
    conn.execute(f"UPDATE operation SET annulee=1 WHERE id IN "
                 f"({','.join('?' * len(liees))})", liees)
    if commit:
        conn.commit()
    return {"operation": operation_id, "ecriture_annulation": res["ecriture_num"],
            "type": op["type"], "montant": op["montant"],
            "operations_annulees": liees}


def supprimer_composant(conn: sqlite3.Connection, composant_id: int,
                        commit: bool = True) -> dict:
    """
    Retire un composant du plan d'immobilisation et CONTRE-PASSE son
    écriture d'acquisition.

    Les composants étaient créables et jamais défaisables : seule la durée
    se corrigeait (route `/immobilisations/composant/<id>/duree`). Une
    valeur brute erronée, un mauvais compte, une date de mise en service
    fausse — tout cela s'écrivait une fois pour toutes, et la seule issue
    était d'ouvrir un dossier neuf. La ventilation d'un prix d'acquisition
    étant précisément l'endroit où l'on tâtonne, l'interdiction ne tenait
    pas.

    Le composant est une donnée de RÉFÉRENTIEL : il se supprime. Son
    écriture d'acquisition est une donnée COMPTABLE : elle ne disparaît
    pas, elle se contre-passe — même geste que `annuler`, pour que le FEC
    garde sa numérotation dense et sa piste d'audit complète.

    Deux garde-fous :
      - un bien cédé ne se remanie plus (ses composants sont sortis du
        bilan par la cession) ;
      - un composant déjà pris dans une clôture ne se supprime pas : sa
        dotation est dans un résultat figé et dans une liasse déjà
        déposée. La sortie de secours reste la restauration d'une
        sauvegarde d'avant clôture (page Dossiers).

    Renvoie {'libelle', 'valeur_brute', 'ecriture_annulation' | None}.
    """
    import cession
    # `bien.date_cession` est une colonne créée à la volée : sur une base
    # antérieure à la cession, elle n'existe pas encore et la lecture
    # échouerait sur « no such column ». Avant la transaction : c'est du DDL.
    cession.assurer_schema(conn)
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row          # isolé : ne modifie pas la connexion
    c = cur.execute(
        "SELECT c.id, c.libelle, c.valeur_brute, c.compte_immo, "
        "c.date_mise_service, b.libelle AS bien, b.date_cession "
        "FROM composant c JOIN bien b ON b.id = c.bien_id "
        "WHERE c.id = ?", (composant_id,)).fetchone()
    if c is None:
        raise ValueError("Composant introuvable — il a peut-être déjà été "
                         "supprimé.")
    if c["date_cession"]:
        raise ValueError(
            f"Le bien « {c['bien']} » a été cédé le {c['date_cession']} : "
            "ses composants sont sortis du bilan et ne se remanient plus.")

    # L'écriture d'acquisition, si elle existe : la création la rend
    # facultative (case « ne pas générer l'écriture d'acquisition », pour un
    # historique déjà porté par les à-nouveaux). On ne contre-passe que ce
    # qui a été réellement passé, et jamais deux fois — la contre-passation
    # porte l'identifiant de l'écriture d'origine dans sa référence de pièce,
    # ce qui rend le deuxième passage impossible sans marqueur en base.
    acq = cur.execute(
        "SELECT e.id, e.exercice_annee FROM ecriture e "
        "JOIN ligne l ON l.ecriture_id = e.id "
        "WHERE e.piece_ref = 'ACQ' AND e.libelle = ? AND l.compte_num = ? "
        "AND ABS(l.debit - ?) < 0.005 "
        "AND NOT EXISTS (SELECT 1 FROM ecriture a "
        "                WHERE a.piece_ref = 'ANNUL-ACQ-' || e.id) "
        "ORDER BY e.id LIMIT 1",
        (f"Acquisition - {c['libelle']}", c["compte_immo"],
         round(float(c["valeur_brute"]), 2))).fetchone()

    # Un composant entré dans une clôture a produit une dotation dans un
    # résultat scellé : le supprimer rendrait la liasse déposée
    # irreproductible. L'année de référence est celle de sa mise en service,
    # à défaut celle de son acquisition.
    reference = None
    if c["date_mise_service"]:
        reference = int(c["date_mise_service"][:4])
    elif acq is not None:
        reference = acq["exercice_annee"]
    if reference is not None:
        clos = conn.execute(
            "SELECT annee FROM exercice WHERE statut = 'clos' AND annee >= ? "
            "ORDER BY annee LIMIT 1", (reference,)).fetchone()
        if clos is not None:
            raise ValueError(
                f"L'exercice {clos[0]} est clos et a déjà amorti « "
                f"{c['libelle']} » : le supprimer fausserait un résultat "
                "figé et une liasse déjà établie. Restaurez une sauvegarde "
                "d'avant clôture (page Dossiers) pour reprendre la saisie.")

    ecriture_annulation = None
    if acq is not None:
        lignes_orig = conn.execute(
            "SELECT compte_num, debit, credit, libelle FROM ligne "
            "WHERE ecriture_id = ?", (acq["id"],)).fetchall()
        res = ecritures.inserer(
            conn, journal="OD", annee=acq["exercice_annee"],
            date=conn.execute("SELECT ecriture_date FROM ecriture WHERE id=?",
                              (acq["id"],)).fetchone()[0],
            libelle=f"Annulation : Acquisition - {c['libelle']}",
            piece_ref=f"ANNUL-ACQ-{acq['id']}", commit=False,
            lignes=[(r[0], round(r[2], 2), round(r[1], 2),
                     f"Annulation - {r[3] or ''}".strip(" -"))
                    for r in lignes_orig])
        ecriture_annulation = res["ecriture_num"]

    conn.execute("DELETE FROM composant WHERE id = ?", (composant_id,))
    if commit:
        conn.commit()
    return {"libelle": c["libelle"],
            "valeur_brute": round(float(c["valeur_brute"]), 2),
            "ecriture_annulation": ecriture_annulation}


# ── Messages rendus à l'utilisateur ───────────────────────────────────────
#
# Le routeur affiche, il ne rédige pas : ces deux phrases expliquent une
# RÈGLE (le sens d'un écart d'amortissement, le sort d'une écriture
# d'acquisition contre-passée) et vivent donc avec elle.

def message_reprise(r: dict) -> str:
    """Compte rendu de `reprendre_amortissements_anterieurs`."""
    comptes = ", ".join(f"{c} : {m:+.2f} €" for c, m in sorted(r["par_compte"].items()))
    # Un écart négatif n'est pas une erreur, mais il ne se lit pas tout
    # seul : les comptes portaient PLUS d'amortissement que le plan n'en
    # calcule, et c'est alors la SAISIE (durée, valeur, date de mise en
    # service) qu'il faut regarder avant de se fier au montant repris.
    sens = ("" if r["total"] >= 0 else
            " Le montant est négatif : les comptes portaient plus "
            "d'amortissement que le plan n'en calcule — vérifiez les durées "
            "et les valeurs de vos composants, qui doivent refléter ce qui a "
            "réellement été pratiqué.")
    return (f"Amortissements antérieurs repris pour {r['total']:.2f} € "
            f"({comptes}) — écriture OD n°{r['ecriture_num']} au 1er janvier. "
            f"Le résultat de l'exercice est inchangé.{sens}")


def message_suppression(r: dict) -> str:
    """Compte rendu de `supprimer_composant`."""
    suite = (f" Son écriture d'acquisition a été contre-passée (OD "
             f"n°{r['ecriture_annulation']}) : le bilan est à jour, et la "
             "piste d'audit conserve les deux écritures."
             if r["ecriture_annulation"] else
             " Aucune écriture d'acquisition n'y était rattachée : rien à "
             "contre-passer.")
    return (f"Composant « {r['libelle']} » supprimé "
            f"({r['valeur_brute']:.2f} €).{suite}")
