# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
# sans autorisation écrite de l'auteur.

"""
Liasse fiscale LMNP au réel simplifié.

Alimente, depuis la base, l'ensemble des tableaux transmis à l'administration :

  - 2031-SD   : récapitulation (résultat fiscal 0, BIC non professionnel 7a/7b)
  - 2031 bis  : détermination du résultat BIC non professionnel
  - 2033-A    : bilan simplifié (actif immobilisé / capitaux propres)
  - 2033-B    : compte de résultat + réintégrations / déductions (extensions)
  - 2033-C    : immobilisations & amortissements par rubrique CERFA
  - 2033-D    : néant (les déficits LMNP sont suivis hors liasse, comme le
                font les prestataires de comptabilité LMNP)
  - Suivi des reports : 39 C (SUIV39C) + déficits LMNP par millésime
  - Aide 2042C-PRO : cases 5NA/5NY et 5GA→5GJ pré-calculées

Convention 2033-B (celle des prestataires de comptabilité LMNP) : le
résultat des locations meublées non
professionnelles est EXCLU de la ligne 352 (déclaré en 2031 bis, cadre I) —
la liasse est donc « ramenée à zéro » par réintégration du déficit ou
déduction du bénéfice, et par la mécanique 39 C.

⚠️ Comme le reste du moteur fiscal : à faire valider par un expert-comptable
avant tout dépôt réel.
"""
from __future__ import annotations

import sqlite3

import plan_immo

import amortissement

TOL = 0.005

# Rubrique CERFA du 2033-C par compte d'immobilisation. La table était ici ET
# dans app.py, sans que l'une référence l'autre : ajouter un compte demandait
# d'y penser deux fois, et un oubli restait invisible (constat D2-05).
RUBRIQUES_2033C = plan_immo.pour_le_2033c()
ORDRE_RUBRIQUES = plan_immo.ordre_rubriques()


# ── Helpers balance ──────────────────────────────────────────────────────────

def _soldes(conn: sqlite3.Connection, annee: int) -> dict[str, float]:
    """Solde net (débit − crédit) par compte sur l'exercice (cumulatif via AN)."""
    rows = conn.execute(
        "SELECT l.compte_num, ROUND(SUM(l.debit - l.credit), 2) "
        "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.exercice_annee = ? GROUP BY l.compte_num", (annee,)).fetchall()
    return {c: s for c, s in rows}


def _somme(soldes: dict[str, float], prefixes: tuple[str, ...],
           exclure: tuple[str, ...] = ()) -> float:
    return round(sum(v for c, v in soldes.items()
                     if c.startswith(prefixes) and c not in exclure), 2)


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> sqlite3.Row | None:
    """Lecture avec accès par nom, sans muter la connexion de l'appelant."""
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row
    return cur.execute(sql, params).fetchone()


def _exercice(conn: sqlite3.Connection, annee: int) -> sqlite3.Row:
    ex = _row(conn, "SELECT * FROM exercice WHERE annee=?", (annee,))
    if ex is None:
        raise ValueError(f"Exercice {annee} inconnu.")
    return ex


def _suivi_39c(conn: sqlite3.Connection, annee: int) -> dict:
    row = _row(conn, "SELECT * FROM suivi_39c WHERE exercice_annee=?", (annee,))
    cles = ("plafond_deductible", "dotation_exercice", "stock_ouverture",
            "report_annee", "utilisation_annee", "stock_cloture")
    if row is None:
        return {k: 0.0 for k in cles}
    return {k: row[k] for k in cles}


def _cloture_fiscale(conn: sqlite3.Connection, annee: int) -> dict:
    try:
        row = _row(conn, "SELECT * FROM cloture_fiscale WHERE exercice_annee=?",
                   (annee,))
    except sqlite3.OperationalError:      # base antérieure : table absente
        row = None
    if row is None:
        return {"retraitements": 0.0, "impute_deficits": 0.0,
                "deficit_cree": None, "revenu_imposable": 0.0}
    return {"retraitements": row["retraitements"],
            "impute_deficits": row["impute_deficits"],
            "deficit_cree": row["deficit_cree"],
            "revenu_imposable": row["revenu_imposable"]}


# ── 2033-B : compte de résultat simplifié + résultat fiscal ─────────────────

def resultat_2033b(conn: sqlite3.Connection, annee: int) -> dict:
    s = _soldes(conn, annee)
    ex = _exercice(conn, annee)
    s39 = _suivi_39c(conn, annee)
    cf = _cloture_fiscale(conn, annee)

    # Produits d'EXPLOITATION seuls en 218/232. Le préfixe « 7 » captait
    # toute la classe, donc le prix de cession (775000) entrait dans le
    # chiffre d'affaires : sur un exercice de cession, la case 218 était
    # gonflée du prix de vente. Le résultat final restait juste — la
    # neutralisation opère ailleurs — mais la ventilation IMPRIMÉE était
    # fausse, et c'est elle que le déclarant recopie (constat E-20).
    #
    # Les trois blocs sont soustraits du total plutôt qu'énumérés par
    # préfixe : un compte de classe 7 oublié dans l'énumération sortirait
    # du résultat en silence, alors qu'ici il retombe en exploitation.
    # Cases confirmées sur le CERFA 2033-B-SD 2026 (n° 15948*08) :
    #   218 Production vendue — Services      (les loyers : une prestation)
    #   230 Autres produits                   (758000 : indemnités, divers)
    #   232 Total des produits d'exploitation (I) = 218 + 230 ici
    #   280 Produits financiers (III)
    #   290 Produits exceptionnels (IV)
    # et la formule de la case 310 : Produits (I + III + IV) − Charges
    # (II + V + VI + VII), VII étant nul en LMNP (pas d'IS).
    produits_tous = round(-_somme(s, ("7",)), 2)
    produits_fin = round(-_somme(s, ("76",)), 2)                  # 280
    produits_exc = round(-_somme(s, ("77",)), 2)                  # 290
    # 75x = autres produits de gestion courante. Depuis que l'indemnité
    # d'assurance va en 758000 (constat E-10), la ranger en 218 gonflerait
    # la « production vendue » d'un produit qui n'en est pas.
    autres_produits = round(-_somme(s, ("75",)), 2)               # 230
    production_vendue = round(produits_tous - produits_fin - produits_exc
                              - autres_produits, 2)               # 218
    produits = round(production_vendue + autres_produits, 2)      # 232
    # Les charges se DÉDUISENT du total de la classe, elles ne s'énumèrent
    # pas. L'énumération par préfixe — 60/61/62, 63, 66, 67, plus le seul
    # compte 681120 — laissait 64 (personnel), 65 (autres charges de
    # gestion), 68 hors 681120 et 69 hors de TOUTE case : sur un FEC de
    # cabinet, 12 000 € de dotation portés en 6811000 disparaissaient de la
    # liasse imprimée tout en restant dans le résultat, et `liasse` divergeait
    # de `fiscal.agregats` d'exactement ce montant.
    #
    # C'est le raisonnement déjà appliqué aux produits (constat E-20), qui
    # n'avait pas été porté sur les charges : ce qui n'est pas reconnu doit
    # RETOMBER dans une case visible, jamais s'évaporer.
    charges_classe6 = _somme(s, ("6",))
    charges_exc = _somme(s, ("67",))                              # 300
    charges_ext = _somme(s, ("60", "61", "62"))                   # 242
    impots = _somme(s, ("63",))                                   # 244
    # 243 « dont CFE et CVAE » : lu sur le compte du plan LIVRÉ. Un plan de
    # cabinet numérote autrement (6351200 relevé sur un bilan réel) et la
    # case reste alors à zéro — aucun préfixe ne distingue la CET des autres
    # impôts directs. Non déterminable sans correspondance de plans.
    dont_cfe = round(s.get("635110", 0.0), 2)                     # 243
    personnel = _somme(s, ("64",))                                # 250
    dotations = _somme(s, ("681",))                               # 254
    charges_fi = _somme(s, ("66",))                               # 294 (intérêts d'emprunt)
    # Charges EXCEPTIONNELLES (classe 67), au premier rang desquelles la
    # valeur comptable des éléments cédés (675000). Les produits étaient
    # captés par le préfixe « 7 » — donc le prix de cession (775000) y
    # entrait — mais aucune charge de classe 67 ne l'était : la ligne 310
    # comptait la recette de la vente sans sa contrepartie. Sur une cession
    # à titre gratuit, le résultat comptable s'en trouvait majoré de toute
    # la valeur nette du bien, en silence.
    # 264 = TOUTE la classe 6 moins le financier et l'exceptionnel. Formulé
    # ainsi, aucun compte de charge ne peut manquer au total, quel que soit
    # le plan du cabinet d'origine.
    total_charges = round(charges_classe6 - charges_fi - charges_exc, 2)  # 264
    # 262 « Autres charges » : le reste, rendu VISIBLE. S'il n'est pas nul,
    # c'est que le FEC porte des comptes de charge que les cases nommées ne
    # couvrent pas — au déclarant de savoir où les reporter.
    autres_charges = round(total_charges - charges_ext - impots
                           - personnel - dotations, 2)            # 262
    # Le bas de compte reste À L'IDENTIQUE : ce qui sort de l'exploitation
    # y revient par les lignes financière et exceptionnelle. Seule la
    # VENTILATION change, jamais le résultat.
    resultat_comptable = round(produits + produits_fin + produits_exc
                               - total_charges - charges_fi
                               - charges_exc, 2)                  # 310

    resultat_fiscal_lmnp = ex["resultat_fiscal"]
    if resultat_fiscal_lmnp is None:                              # non clôturé
        # Exercice OUVERT : la table de clôture n'existe pas encore, donc
        # cf["retraitements"] vaut 0 et la liasse provisoire ignorait le
        # fonds ALUR pourtant déjà saisi. Ce retraitement n'est PAS une
        # estimation — la charge est comptabilisée, sa non-déductibilité
        # est une règle de droit. Il a donc sa place dans les tableaux.
        # La DOTATION de l'année, elle, n'est pas comptabilisée : elle
        # relève de la projection (bloc « projection_cloture »), pas des
        # tableaux, qui doivent refléter les écritures.
        import fiscal as _fiscal
        retraitements = _fiscal.retraitement_automatique(conn, annee)
        # La CESSION doit être neutralisée ici comme elle l'est à la
        # clôture : le prix de vente est déduit et la valeur comptable
        # réintégrée, le régime des plus-values des particuliers
        # s'appliquant hors BIC. Sans ces deux termes, la liasse
        # provisoire annonçait une base imposable majorée de TOUTE la
        # plus-value — sur la case 5NA que le déclarant recopie. Le
        # commentaire de `_calcul_fiscal` dit être la « source unique »
        # de cette règle : la liasse ne l'appliquait pas.
        _ag = _fiscal.agregats(conn, annee)
        neutralisation = round(_ag["vnc_cession"] - _ag["produits_cession"], 2)
        resultat_fiscal_lmnp = round(resultat_comptable
                                     + s39["report_annee"]
                                     - s39["utilisation_annee"]
                                     + retraitements
                                     + neutralisation, 2)
    else:
        retraitements = cf["retraitements"]      # figé par la clôture
        import fiscal as _fiscal
        _ag = _fiscal.agregats(conn, annee)
        neutralisation = round(_ag["vnc_cession"] - _ag["produits_cession"], 2)

    # Réintégrations / déductions, convention de place : ligne 352 = 0.
    reint_318 = s39["report_annee"]                               # amort. excédentaires
    reint_divers, deduc_divers = [], []
    if retraitements > TOL:
        reint_divers.append(("Retraitements divers (ex. fonds travaux ALUR)",
                             round(retraitements, 2)))
    elif retraitements < -TOL:
        deduc_divers.append(("Retraitements divers en déduction",
                             round(-cf["retraitements"], 2)))
    if resultat_fiscal_lmnp < -TOL:
        reint_divers.append(("Résultat LMNP non soumis aux contributions sociales",
                             round(-resultat_fiscal_lmnp, 2)))
    if s39["utilisation_annee"] > TOL:
        deduc_divers.append(("Dotations aux amortissements reprises (article 39 C)",
                             s39["utilisation_annee"]))
    # La cession figure au compte de résultat (775000 en produit, 675000 en
    # charge) mais relève du régime des plus-values des particuliers : elle
    # sort du résultat BIC par une réintégration de la valeur comptable et
    # une déduction du prix. Sans ces deux lignes, la 352 valait la
    # plus-value au lieu de zéro, et TOUTE liasse d'exercice de cession
    # sortait auto-déclarée non conforme.
    if neutralisation > TOL:
        reint_divers.append(("Valeur comptable des éléments cédés "
                             "(régime des particuliers)", neutralisation))
    elif neutralisation < -TOL:
        deduc_divers.append(("Produit de cession (régime des particuliers)",
                             round(-neutralisation, 2)))
    if resultat_fiscal_lmnp > TOL:
        deduc_divers.append(("Résultat LMNP non soumis aux contributions sociales",
                             round(resultat_fiscal_lmnp, 2)))

    reint_330 = round(sum(m for _, m in reint_divers), 2)
    deduc_350 = round(sum(m for _, m in deduc_divers), 2)
    ligne_352 = round(resultat_comptable + reint_318 + reint_330 - deduc_350, 2)

    return {
        "produits_218": production_vendue,
        "autres_produits_230": autres_produits,
        "total_produits_232": produits,
        "produits_financiers_280": produits_fin,
        "produits_exceptionnels_290": produits_exc,
        "charges_externes_242": charges_ext,
        "impots_244": impots, "dont_cfe_243": dont_cfe,
        "personnel_250": personnel, "autres_charges_262": autres_charges,
        "dotations_254": dotations, "total_charges_264": total_charges,
        "charges_financieres_294": charges_fi,
        "resultat_exploitation_270": round(produits - total_charges, 2),
        "benefice_ou_perte_310": resultat_comptable,
        "charges_exceptionnelles_300": charges_exc,
        "reintegration_amort_318": reint_318,
        "reintegration_divers_330": reint_330,
        "reintegrations_detail": reint_divers,
        "deductions_350": deduc_350,
        "deductions_detail": deduc_divers,
        "resultat_fiscal_352": ligne_352,          # doit valoir 0
        "resultat_fiscal_370": ligne_352,
        "resultat_fiscal_lmnp": round(resultat_fiscal_lmnp, 2),
    }


# ── 2033-A : bilan simplifié ─────────────────────────────────────────────────

def bilan_2033a(conn: sqlite3.Connection, annee: int) -> dict:
    s = _soldes(conn, annee)
    b = resultat_2033b(conn, annee)

    types = dict(conn.execute("SELECT numero, type FROM compte").fetchall())
    immo_brut = round(sum(v for c, v in s.items()
                          if types.get(c) == "actif" and c.startswith("2")), 2)
    amort = round(-sum(v for c, v in s.items()
                       if types.get(c) == "amortissement"), 2)   # créditeur → positif
    immo_net = round(immo_brut - amort, 2)

    resultat = b["benefice_ou_perte_310"]
    # Capitaux propres = actif net (bilan LMNP sans dettes ni trésorerie 512).
    total_passif = immo_net
    capital_120 = round(total_passif - resultat, 2)

    return {
        "immo_corporelles_brut_028": immo_brut,
        "amortissements_030": amort,
        "immo_corporelles_net": immo_net,
        "total_actif_110": immo_brut, "total_actif_net_112": immo_net,
        "capital_individuel_120": capital_120,
        "resultat_exercice_136": resultat,
        "total_capitaux_142": total_passif,
        "total_passif_180": total_passif,
        "equilibre": abs(immo_net - total_passif) < TOL,
    }


# ── 2033-C : immobilisations & amortissements ────────────────────────────────

def _anomalies_du_moteur(conn: sqlite3.Connection, annee: int) -> list[dict]:
    """Anomalies de `controles.controler`, sous une forme imprimable.

    Sa propre défaillance ne doit pas empêcher d'éditer la liasse : elle
    devient une ligne d'anomalie, pas une exception.
    """
    import controles as _controles
    try:
        anos = _controles.controler(conn, annee)
    except Exception as exc:                          # noqa: BLE001
        return [{"niveau": "BLOQUANT", "code": "CONTROLES_INDISPONIBLES",
                 "message": f"Les contrôles de cohérence n'ont pas pu être "
                            f"exécutés ({type(exc).__name__} : {exc})."}]
    return [{"niveau": a.niveau, "code": a.code, "message": a.message}
            for a in anos]


def _fiscal_agregats_cession(conn: sqlite3.Connection, annee: int) -> dict:
    """{'produit', 'valeur_comptable'} des cessions de l'exercice, ou {}."""
    import fiscal as _fiscal
    ag = _fiscal.agregats(conn, annee)
    produit = round(ag.get("produits_cession", 0.0), 2)
    vnc = round(ag.get("vnc_cession", 0.0), 2)
    if abs(produit) < TOL and abs(vnc) < TOL:
        return {}
    return {"produit": produit, "valeur_comptable": vnc}


def compte_amortissement(conn: sqlite3.Connection, composant_id: int) -> str:
    r = conn.execute("SELECT compte_amort FROM composant WHERE id=?",
                     (composant_id,)).fetchone()
    return (r[0] or "") if r else ""


def _mouvements_de_cession(conn: sqlite3.Connection, bien_id: int,
                           annee: int) -> dict:
    """Mouvements d'amortissement RÉELLEMENT écrits lors de la cession de ce
    bien, par compte : la dotation complémentaire et la diminution qui solde.

    Lus dans les écritures, et non recalculés depuis le plan : c'est le
    même principe qu'en passe L pour la sortie elle-même — ce qu'on
    présente au déclarant doit être ce qui a été comptabilisé.

    Les deux pièces portent l'identifiant du bien depuis la passe I, ce qui
    les rattache sans ambiguïté. `parts` répartit chaque compte entre les
    composants du bien qui l'utilisent, au prorata de leur valeur brute —
    l'identité lorsqu'ils ne sont qu'un, le cas courant.
    """
    out: dict[str, dict] = {}
    for piece, cle in ((f"DAA-CESSION-{bien_id}", "dotation"),
                       (f"CESSION-{bien_id}", "diminution")):
        signe = -1.0 if cle == "dotation" else 1.0   # crédit pour la dotation
        for compte, montant in conn.execute(
                "SELECT l.compte_num, ROUND(SUM(l.debit - l.credit), 2) "
                "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
                "WHERE e.exercice_annee=? AND e.piece_ref=? "
                "AND l.compte_num LIKE '28%' GROUP BY l.compte_num",
                (annee, piece)):
            out.setdefault(compte, {})[cle] = round(signe * float(montant), 2)
    for compte, valeurs in out.items():
        membres = conn.execute(
            "SELECT id, valeur_brute FROM composant WHERE bien_id=? "
            "AND compte_amort=?", (bien_id, compte)).fetchall()
        total = sum(float(v) for _i, v in membres) or 1.0
        valeurs["parts"] = {i: float(v) / total for i, v in membres}
        valeurs.setdefault("dotation", 0.0)
        valeurs.setdefault("diminution", 0.0)
    return out


def _amortissements_traces(conn: sqlite3.Connection, composant_id: int,
                           annee: int) -> tuple[float | None, float | None]:
    """(dotation, cumul_fin) enregistrés à la clôture de `annee`, ou (None,
    None) si aucune trace — un exercice pas encore clôturé, ou antérieur à
    la tenue de cette table."""
    try:
        r = conn.execute(
            "SELECT dotation, cumul_fin FROM plan_amortissement "
            "WHERE composant_id=? AND exercice_annee=?",
            (composant_id, annee)).fetchone()
    except sqlite3.OperationalError:
        return None, None
    return (None, None) if r is None else (float(r[0]), float(r[1]))


def immobilisations_2033c(conn: sqlite3.Connection, annee: int) -> dict:
    rows = conn.execute(
        "SELECT id, libelle, valeur_brute, duree_annees, date_mise_service, "
        "compte_immo, amortissable, bien_id FROM composant "
        "ORDER BY id").fetchall()
    # Les composants d'un bien CÉDÉ sont sortis du bilan : les laisser dans
    # le tableau des immobilisations faisait diverger la 2033-C du bilan de
    # façon permanente, sans que rien ne l'explique. La colonne
    # `date_cession` n'existe que sur les bases où une cession a eu lieu
    # (cession.assurer_schema la crée) : on filtre donc seulement si elle
    # est là, plutôt que d'imposer une migration à tous les dossiers.
    # Un bien cédé sort du bilan — mais l'exercice de sa cession doit
    # MONTRER cette sortie. L'exclusion portait sur toutes les années à
    # partir de la cession, l'année de vente comprise : le tableau
    # n'affichait alors ni le brut d'ouverture, ni la dotation de sortie,
    # ni la diminution, seulement des zéros. Les soldes finaux étaient
    # justes, et les contrôles ne comparant que les soldes finaux, ils
    # approuvaient. 12 000 € de brut et 1 795,07 € de mouvements
    # d'amortissement manquaient au déclarant.
    #
    # On distingue donc deux situations : cédé AVANT l'exercice (le bien
    # n'a plus rien à y faire) et cédé PENDANT (ses mouvements sont ceux de
    # l'exercice, et ses soldes finaux sont nuls).
    try:
        cedes_avant, cedes_annee = set(), set()
        for bid, date_cession in conn.execute(
                "SELECT id, date_cession FROM bien "
                "WHERE date_cession IS NOT NULL AND date_cession <> ''"):
            if str(date_cession)[:4] < str(annee):
                cedes_avant.add(bid)
            elif str(date_cession)[:4] == str(annee):
                cedes_annee.add(bid)
    except sqlite3.OperationalError:
        cedes_avant, cedes_annee = set(), set()
    if cedes_avant:
        # Index positionnel et non nommé : selon l'appelant, la connexion
        # peut ne pas avoir de row_factory, et les lignes sont alors des
        # tuples nus. bien_id est la 8e colonne du SELECT ci-dessus.
        rows = [x for x in rows if x[7] not in cedes_avant]
    mouvements = {b: _mouvements_de_cession(conn, b, annee)
                  for b in cedes_annee}

    rub = {k: {"libelle": lib, "case_immo": ci, "case_amort": ca,
               "brut_debut": 0.0, "augmentations": 0.0, "diminutions": 0.0,
               "brut_fin": 0.0, "amort_debut": 0.0, "dotation": 0.0,
               "amort_diminutions": 0.0, "amort_fin": 0.0}
           for compte, (k, lib, ci, ca) in RUBRIQUES_2033C.items()}
    detail = []

    for cid, lib, vb, duree, dms, compte, amortissable, _bien in rows:
        resolu = plan_immo.resoudre(compte)
        cle = RUBRIQUES_2033C.get(resolu, ("autres_immo",))[0]
        r = rub[cle]
        annee_entree = int((dms or f"{annee}-01-01")[:4])
        if annee_entree < annee:
            r["brut_debut"] += vb
        elif annee_entree == annee:
            r["augmentations"] += vb
        else:
            continue                       # entré après l'exercice : hors liasse
        if _bien in cedes_annee:
            # Entré (ou déjà là) puis sorti dans le même exercice : la
            # diminution efface le brut, et le solde final est nul.
            r["diminutions"] += vb
            sortis = mouvements[_bien].get(compte_amortissement(conn, cid), {})
            part = sortis.get("parts", {}).get(cid, 0.0)
            dot = round(sortis.get("dotation", 0.0) * part, 2)
            dim = round(sortis.get("diminution", 0.0) * part, 2)
            r["dotation"] += dot
            r["amort_diminutions"] += dim
            r["amort_debut"] += round(dim - dot, 2)
            detail.append({"libelle": lib, "valeur_brute": round(vb, 2),
                           "duree": duree, "dotation": round(dot, 2),
                           "cumul_fin": 0.0, "vnc_fin": 0.0,
                           "sorti": True})
            continue
        r["brut_fin"] += vb

        dot = cum_fin = 0.0
        if amortissable and duree:
            # LA TRACE D'ABORD, le recalcul ensuite. `etat()` reconstruit le
            # plan depuis la durée ACTUELLE du composant : modifier cette
            # durée réécrivait donc le tableau d'un exercice déjà CLOS, dont
            # les amortissements étaient pourtant arrêtés — la route
            # annonçait « durée portée à 20 ans », et le 2033-C de l'exercice
            # précédent passait de 1 200 € à 600 €, cependant que le bilan et
            # le FEC, eux, ne bougeaient pas. La trace écrite à la clôture
            # dans `plan_amortissement` dit ce qui a été réellement
            # comptabilisé : c'est elle qui fait foi quand elle existe.
            dot, cum_fin = _amortissements_traces(conn, cid, annee)
            _, cum_deb = _amortissements_traces(conn, cid, annee - 1)
            if dot is None or cum_fin is None:
                dot, cum_fin, _ = amortissement.etat(vb, duree, dms, annee)
            if cum_deb is None:
                _, cum_deb, _ = amortissement.etat(vb, duree, dms, annee - 1)
            r["amort_debut"] += cum_deb
            r["dotation"] += dot
            r["amort_fin"] += cum_fin
        detail.append({"libelle": lib, "valeur_brute": round(vb, 2),
                       "duree": duree, "dotation": round(dot, 2),
                       "cumul_fin": round(cum_fin, 2),
                       "vnc_fin": round(vb - cum_fin, 2)})

    colonnes = ("brut_debut", "augmentations", "diminutions", "brut_fin",
                "amort_debut", "dotation", "amort_diminutions", "amort_fin")
    for r in rub.values():
        for k in colonnes:
            r[k] = round(r[k], 2)

    totaux = {k: round(sum(r[k] for r in rub.values()), 2) for k in colonnes}
    return {"rubriques": [rub[k] for k in ORDRE_RUBRIQUES],
            "totaux": totaux, "detail_composants": detail}


# ── Suivi des reports (39 C + déficits LMNP) ─────────────────────────────────

def suivi_reports(conn: sqlite3.Connection, annee: int) -> dict:
    s39 = _suivi_39c(conn, annee)
    # Stock 39 C PERDU à la cession d'un bien. La ventilation par bien
    # l'enregistre (colonne sortie_bien) et le PDF le montre, mais le suivi
    # global ne le disait pas : à l'écran, le stock passait de 8 000 € à 0
    # sans un mot, et le « total des reports disponibles » chutait comme
    # s'il avait été utilisé. Un montant qui disparaît doit s'expliquer.
    try:
        sortie_39c = conn.execute(
            "SELECT COALESCE(ROUND(SUM(COALESCE(sortie_bien, 0)), 2), 0) "
            "FROM suivi_39c_bien WHERE exercice_annee=?", (annee,)).fetchone()[0]
    except sqlite3.OperationalError:
        sortie_39c = 0.0
    import json
    snapshot = None
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='suivi_deficits'").fetchone():
        snapshot = conn.execute(
            "SELECT details_json FROM suivi_deficits WHERE exercice_annee=?",
            (annee,)).fetchone()
    if snapshot is not None:
        deficits = json.loads(snapshot[0])
    else:
        # L'historique d'avant migration ne peut pas être déduit du solde
        # courant : refuser une réédition trompeuse, sans inventer de stocks.
        clos = conn.execute("SELECT 1 FROM exercice WHERE annee>=? AND statut='clos'",
                            (annee,)).fetchone()
        if clos:
            raise ValueError(
                f"Historique des déficits indisponible pour {annee} : "
                "exercice clos sans suivi par millésime. Utilisez les archives "
                "de déclaration ou une sauvegarde antérieure à la clôture.")
        deficits = [dict(annee_origine=a, montant_initial=round(m, 2),
                         solde=round(so, 2), annee_expiration=e,
                         solde_ouverture=round(so, 2), impute=0,
                         perte_peremption=0)
                    for a, m, so, e in conn.execute(
                        "SELECT annee_origine, montant_initial, solde, annee_expiration "
                        "FROM deficit_lmnp WHERE annee_origine<=? ORDER BY annee_origine, id",
                        (annee,))]
    for d in deficits:
        d["perime"] = d["annee_expiration"] is not None and annee > d["annee_expiration"]
    deficits = [d for d in deficits if d["solde"] or d["solde_ouverture"]
                or d["perte_peremption"]]
    total_deficits = round(sum(d["solde"] for d in deficits
                               if not d["perime"]), 2)
    total_perimes = round(sum(d["perte_peremption"] or d["solde"] for d in deficits
                              if d["perime"]), 2)
    import fiscal as _fiscal
    return {"suivi_39c": s39, "deficits": deficits,
            "suivi_39c_par_bien": _fiscal.suivi_39c_par_bien(conn, annee),
            "total_deficits": total_deficits,
            "total_deficits_perimes": total_perimes,
            "sortie_39c": round(sortie_39c or 0.0, 2),
            "total_restant": round(s39["stock_cloture"] + total_deficits, 2)}


# ── 2031 / 2031 bis / aide 2042C-PRO ─────────────────────────────────────────

def recap_2031(conn: sqlite3.Connection, annee: int) -> dict:
    b = resultat_2033b(conn, annee)
    rf = b["resultat_fiscal_lmnp"]
    return {"resultat_fiscal_1": b["resultat_fiscal_370"],   # 0
            "bic_non_pro_7a_benefice": round(rf, 2) if rf > TOL else None,
            "bic_non_pro_7b_deficit": round(-rf, 2) if rf < -TOL else None}


def aide_2042c(conn: sqlite3.Connection, annee: int) -> dict:
    """Cases pré-calculées pour la 2042C-PRO (régime réel, cas général)."""
    b = resultat_2033b(conn, annee)
    rep = suivi_reports(conn, annee)
    rf = b["resultat_fiscal_lmnp"]

    # 5GA (année N-10) → 5GJ (année N-1) : déficits antérieurs non déduits.
    cases_lettres = ["5GA", "5GB", "5GC", "5GD", "5GE",
                     "5GF", "5GG", "5GH", "5GI", "5GJ"]
    # Ouverture réellement enregistrée, regroupée par année d'origine.
    solde_par_origine = {}
    for d in rep["deficits"]:
        if not d["perime"] and d["annee_origine"] < annee:
            origine = d["annee_origine"]
            solde_par_origine[origine] = round(
                solde_par_origine.get(origine, 0) + d["solde_ouverture"], 2)
    from decimal import Decimal, ROUND_HALF_UP

    def euro(montant):
        return int(Decimal(str(montant)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    cases_deficits = []
    for i, lettre in enumerate(cases_lettres):
        origine = annee - 10 + i
        montant = solde_par_origine.get(origine)
        if montant is not None and euro(montant) > 0:
            cases_deficits.append({"case": lettre, "annee_origine": origine,
                                   "montant": euro(montant)})
    return {"case_5NA": euro(rf) if rf > TOL else None,
            "case_5NY": euro(-rf) if rf < -TOL else None,
            "cases_deficits_anterieurs": cases_deficits,
            "note": ("Montants indicatifs, arrondis à l'euro. À vérifier au "
                     "niveau du foyer fiscal, notamment en présence d'autres "
                     "activités de location meublée.")}


# ── Assemblage + contrôles internes ─────────────────────────────────────────

def _ops_ecart_materiel(ecart: float, reference: float) -> bool:
    import operations as _ops
    return _ops.ecart_materiel(ecart, reference)


def _amortissements_concordent(conn, annee, b2033c, b2033a) -> bool:
    """
    Le tableau 2033-C déroule le PLAN d'amortissement ; la case 030 du bilan
    lit les COMPTES. Sur un exercice OUVERT, l'écart normal entre les deux
    vaut exactement la dotation de l'exercice — écrite seulement à la
    clôture. Ce n'est pas une anomalie : c'est la définition même d'un
    exercice en cours.

    Signaler « ANOMALIE » dans ce cas revenait à afficher une alerte rouge
    sur tout dossier consulté avant sa clôture, y compris le dossier de
    démonstration qu'un débutant ouvre en premier. On ne conserve donc
    l'anomalie que pour l'écart RÉSIDUEL — celui qui, lui, ne se résorbera
    pas tout seul (amortissements antérieurs jamais repris).
    """
    import operations as _ops
    ecart = round(b2033c["totaux"]["amort_fin"]
                  - b2033a["amortissements_030"], 2)
    reference = b2033c["totaux"]["amort_fin"]
    proj = _projection_cloture(conn, annee)
    if proj is not None:
        # Exercice ouvert : la dotation à venir explique l'écart attendu.
        ecart = round(ecart - proj["dotation_previsionnelle"], 2)
    return not _ops.ecart_materiel(ecart, reference)


def _projection_cloture(conn: sqlite3.Connection, annee: int) -> dict | None:
    """
    Ce que donnerait la clôture si elle avait lieu maintenant — None si
    l'exercice est déjà clos.

    Pourquoi un bloc SÉPARÉ plutôt que des chiffres injectés dans les
    tableaux : la dotation aux amortissements n'est comptabilisée qu'à la
    clôture, et les tableaux 2033-A / 2033-B doivent refléter les
    ÉCRITURES, pas une prévision (le bilan d'ouverture d'un dossier repris
    doit rester réconciliable avec celui du prestataire précédent). Mais
    sans cette projection, le déclarant lisait toute l'année un « résultat
    fiscal » qui ignorait l'amortissement de l'exercice — pour un dossier
    réel : 395 € annoncés là où la clôture donnait ~25 €.

    La 2033-C, elle, déroule le PLAN d'amortissement : c'est sa nature, et
    c'est pourquoi elle peut légitimement afficher une dotation que la
    2033-B ne voit pas encore.
    """
    statut = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                          (annee,)).fetchone()
    if statut is None or statut[0] != "ouvert":
        return None
    import fiscal as _fiscal
    sim = _fiscal.simuler(conn, annee)
    return {
        "dotation_previsionnelle": sim["dotation_previsionnelle"],
        "resultat_comptable_projete": sim["agregats"]["resultat_comptable"],
        "resultat_fiscal_projete": sim["resultat_fiscal"],
        "report_39c_projete": sim["suivi_39c"]["report_annee"],
        "utilisation_39c_projetee": sim["suivi_39c"]["utilisation_annee"],
        "retraitements": sim["autres_retraitements"],
    }


def _explication_ecart_amortissements(conn, annee, b2033c, b2033a) -> str:
    """Un écart de cette nature a presque toujours la même cause : un bien
    déjà amorti entré au seul brut. On le dit, au lieu d'aligner deux
    nombres muets."""
    ecart = round(b2033c["totaux"]["amort_fin"]
                  - b2033a["amortissements_030"], 2)
    if ecart <= 0:
        return (" — le bilan porte plus d'amortissements que le plan : "
                "vérifiez les dotations saisies à la main.")
    statut = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                          (annee,)).fetchone()
    if statut and statut[0] == "ouvert":
        proj = _projection_cloture(conn, annee)
        dotation = proj["dotation_previsionnelle"] if proj else 0.0
        reliquat = round(ecart - dotation, 2)
        if not _ops_ecart_materiel(reliquat, ecart):
            return (f" — écart de {ecart:.2f} €, soit la dotation "
                    "de l'exercice, qui sera comptabilisée à la clôture. "
                    "Rien à corriger.")
        return (f" — écart de {ecart:.2f} €, dont {dotation:.2f} € de "
                f"dotation à venir et {reliquat:.2f} € qui ne se "
                "résorberont pas seuls : ce sont les amortissements déjà "
                "courus avant l'entrée du bien dans le logiciel (page "
                "Immobilisations, « Reprendre les amortissements "
                "antérieurs »).")
    return (f" — écart de {ecart:.2f} € : ce sont les amortissements déjà "
            "courus avant l'entrée du bien dans le logiciel, jamais "
            "comptabilisés. Le bien a été saisi à sa valeur BRUTE sans "
            "son cumul d'amortissement. Corrigez depuis la page "
            "Immobilisations (« Reprendre les amortissements "
            "antérieurs ») : le résultat n'est pas touché, seul le bilan "
            "est remis à l'endroit.")


def generer(conn: sqlite3.Connection, annee: int) -> dict:
    """Assemble la liasse complète et exécute des contrôles de cohérence."""
    ex = _exercice(conn, annee)
    exploitant = _row(conn, "SELECT * FROM exploitant LIMIT 1")
    b2033b = resultat_2033b(conn, annee)
    b2033a = bilan_2033a(conn, annee)
    b2033c = immobilisations_2033c(conn, annee)
    reports = suivi_reports(conn, annee)
    r2031 = recap_2031(conn, annee)
    aide = aide_2042c(conn, annee)
    cf = _cloture_fiscale(conn, annee)

    controles = [
        ("Bilan équilibré (actif net = capitaux propres)",
         b2033a["equilibre"],
         f"actif {b2033a['immo_corporelles_net']:.2f} € / "
         f"passif {b2033a['total_passif_180']:.2f} €"),
        ("2033-B ligne 352 = 0 (résultat LMNP exclu, déclaré en 2031 bis)",
         abs(b2033b["resultat_fiscal_352"]) < TOL,
         f"{b2033b['resultat_fiscal_352']:.2f} €"),
        ("2033-C : total brut fin = somme des valeurs brutes",
         abs(b2033c["totaux"]["brut_fin"]
             - b2033a["immo_corporelles_brut_028"]) < TOL,
         f"{b2033c['totaux']['brut_fin']:.2f} € / "
         f"{b2033a['immo_corporelles_brut_028']:.2f} €"),
        ("2033-C : amortissements fin = case 030 du bilan",
         _amortissements_concordent(conn, annee, b2033c, b2033a),
         f"{b2033c['totaux']['amort_fin']:.2f} € / "
         f"{b2033a['amortissements_030']:.2f} €"
         + ("" if abs(b2033c["totaux"]["amort_fin"]
                      - b2033a["amortissements_030"]) < TOL else
            _explication_ecart_amortissements(conn, annee, b2033c, b2033a))),
        ("Résultat fiscal 2033-B = résultat fiscal de clôture",
         ex["resultat_fiscal"] is None
         or abs(b2033b["resultat_fiscal_lmnp"] - ex["resultat_fiscal"]) < TOL,
         f"{b2033b['resultat_fiscal_lmnp']:.2f} €"),
    ]

    # Signal EXPLICITE d'une cession dans l'exercice, pour que le rendu
    # n'ait pas à le déduire de montants. Il vaut aussi pour une cession à
    # titre gratuit, où le prix est nul mais la valeur comptable sort.
    ag_cession = _fiscal_agregats_cession(conn, annee)

    return {
        "annee": annee,
        "cession_de_l_exercice": ag_cession,
        "statut_exercice": ex["statut"],
        "provisoire": ex["statut"] != "clos",
        "exploitant": dict(exploitant) if exploitant else None,
        "page_garde": {
            "ca_ht": b2033b["produits_218"],
            "resultat_fiscal": b2033b["resultat_fiscal_lmnp"],
            "deficit_lmnp": (round(-b2033b["resultat_fiscal_lmnp"], 2)
                             if b2033b["resultat_fiscal_lmnp"] < -TOL else 0.0),
            "revenu_imposable": cf["revenu_imposable"],
            "restant_39c": reports["suivi_39c"]["stock_cloture"],
            "restant_deficits": reports["total_deficits"],
            "restant_total": reports["total_restant"],
        },
        "f2031": r2031, "f2033a": b2033a, "f2033b": b2033b,
        "f2033c": b2033c, "reports": reports, "aide_2042c": aide,
        "projection_cloture": _projection_cloture(conn, annee),
        "controles": [{"nom": n, "ok": bool(ok), "detail": d}
                      for n, ok, d in controles],
        # Les anomalies du MOTEUR DE CONTRÔLES, distinctes des cinq
        # vérifications internes ci-dessus. Les deux ensembles n'étaient
        # pas reliés : le document remis pouvait afficher cinq « conforme »
        # en vert alors qu'une anomalie BLOQUANTE — 800 € en compte
        # d'attente — attendait dans le moteur. Le filigrane « provisoire »
        # ne restitue ni l'anomalie ni son montant.
        "anomalies": _anomalies_du_moteur(conn, annee),
        "conforme": all(ok for _, ok, _ in controles),
    }
