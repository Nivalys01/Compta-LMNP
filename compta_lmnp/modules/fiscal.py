# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Jalon J5 — Moteurs fiscaux : limitation art. 39 C du CGI et déficits LMNP.

DEUX FILES STRICTEMENT DISTINCTES (jamais cumulées) :
  - Report 39 C : amortissements non déductibles, reportables SANS limite de durée.
  - Déficit LMNP : imputable sur bénéfices de même nature, PÉREMPTION à 10 ans.

⚠️ AVERTISSEMENT — ce module code la mécanique observée dans les logiciels du marché, mais le calcul
du résultat fiscal d'un LMNP au réel comporte des subtilités (retraitements divers,
ventilation des charges afférentes) qui doivent être validées par un expert-comptable
avant tout usage en déclaration réelle.

⚠️ `autres_retraitements` — NE PAS y saisir le fonds de travaux ALUR. Il est
réintégré AUTOMATIQUEMENT par `retraitement_automatique()`, à partir des
écritures de ventilation d'appel de charges, et les deux montants
S'ADDITIONNENT : le saisir ici le compterait deux fois et gonflerait le
résultat imposable. Ce paramètre ne sert qu'à un retraitement que le
logiciel ne connaît pas — un redressement demandé par un comptable, par
exemple. (Cette docstring donnait précisément le contre-exemple à ne pas
suivre : signalé en revue adversariale.)
"""
from __future__ import annotations
import sqlite3
import parametres
import gabarits as _g

TOL = 0.005

# ── Familles de comptes, reconnues par PRÉFIXE et non par égalité ─────────
#
# Tout ce module identifiait ses comptes par `l.compte_num = '681120'` ou
# `IN ('622610', …)`. Le plan livré tient sur six chiffres ; un cabinet en
# utilise sept, et la reprise d'un FEC crée ces comptes tels quels. Chaque
# égalité stricte devenait alors une qualification fiscale MANQUÉE, en
# silence et sans qu'aucun total ne bouge :
#
#   - une dotation en 6811200 n'était plus une dotation : elle tombait dans
#     les charges ordinaires, et son excédent devenait un DÉFICIT — soumis
#     à la péremption décennale — au lieu d'un report 39 C sans limite ;
#   - des honoraires en 6226100 n'étaient plus exclus du plafond ;
#   - un produit de cession en 7750000 n'était plus neutralisé, et gonflait
#     le plafond comme s'il s'agissait d'un loyer.
#
# Un compte se reconnaît donc à sa RACINE PCG, qui est ce que le plan
# comptable normalise ; ses subdivisions en héritent, par construction.
PREFIXE_DOTATION = "6811"        # dotations aux amortissements sur immo.
PREFIXE_PRODUIT_CESSION = "775"  # produits de cession d'éléments d'actif
PREFIXE_VNC_CESSION = "675"      # valeur comptable des éléments cédés

# Produits qui ne sont PAS des loyers acquis. Le plafond de l'article 39 C
# se calcule sur « le loyer acquis diminué des autres charges afférentes au
# bien » : un produit financier, un produit exceptionnel, une reprise sur
# provision ou un transfert de charges n'augmentent pas la capacité
# d'amortissement de la location. Tous les produits de classe 7 y étaient
# comptés — un produit financier fictif de 1 000 € absorbait donc
# immédiatement 1 000 € d'amortissement au lieu de les faire reporter.
PREFIXES_PRODUITS_HORS_LOYERS = ("76", "77", "78", "79")


def _sql_prefixe(colonne: str, prefixes) -> tuple[str, list]:
    """(fragment SQL, paramètres) testant l'appartenance par préfixe."""
    if isinstance(prefixes, str):
        prefixes = (prefixes,)
    if not prefixes:
        return "0", []
    return ("(" + " OR ".join(f"{colonne} LIKE ?" for _ in prefixes) + ")",
            [f"{p}%" for p in prefixes])


def est_compte_dotation(numero: str) -> bool:
    """Le compte est-il un compte de dotation aux amortissements ?"""
    return (numero or "").strip().startswith(PREFIXE_DOTATION)


# --- Agrégats comptables de l'exercice (lus dans les écritures) -------------

def comptes_hors_plafond_39c(conn: sqlite3.Connection) -> list[str]:
    """
    Comptes de charges EXCLUS du calcul du plafond 39 C.

    Art. 39 C, II-2 du CGI : la déduction de l'amortissement est limitée au
    montant du loyer acquis diminué des autres charges AFFÉRENTES AU BIEN
    loué. Les charges de structure de l'activité (honoraires comptables,
    CFE) ne sont pas afférentes au bien : elles ne diminuent pas le plafond.
    Vérifié case par case contre les liasses réelles de référence 2023-2025 (page
    « Formation du résultat fiscal », colonne « Calcul plafond des amort.
    déduct. » vide pour ces lignes). Table extensible par l'utilisateur.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS compte_hors_plafond_39c ("
                 "numero TEXT PRIMARY KEY REFERENCES compte(numero))")
    # Honoraires comptables et CFE : charges de structure de l'activité.
    # 675000 (VNC des actifs cédés) : charge de CESSION, pas de location —
    # elle ne diminue jamais le plafond des amortissements déductibles.
    for numero in ("622610", "635110", "675000"):
        conn.execute("INSERT OR IGNORE INTO compte_hors_plafond_39c "
                     "SELECT ? WHERE EXISTS (SELECT 1 FROM compte WHERE numero=?)",
                     (numero, numero))
    return [r[0] for r in conn.execute("SELECT numero FROM compte_hors_plafond_39c")]


def racines_hors_plafond_39c(conn: sqlite3.Connection) -> list[str]:
    """Les mêmes exclusions, réduites à leur RACINE.

    La table ne peut contenir que des comptes existants (clé étrangère), ce
    qui la lie au plan livré à six chiffres. Les honoraires comptables d'un
    cabinet arrivent en 6226100 : le compte exact n'y figure pas, l'exclusion
    ne jouait pas, et 500 € passaient du déficit au report 39 C sans qu'un
    contrôle ne le voie. On compare donc par préfixe, et une subdivision
    hérite de l'exclusion de sa racine.

    La racine `675` est ajoutée d'office : la valeur comptable d'un élément
    cédé est une charge de CESSION, jamais afférente à la location, et elle
    doit être exclue même si le compte 675000 du plan livré est absent de la
    base (référentiel minimal, dossier importé).
    """
    racines = {r for r in comptes_hors_plafond_39c(conn)}
    racines.add(PREFIXE_VNC_CESSION)
    # Une racine qui en préfixe une autre la rend inutile : on garde la plus
    # courte, pour que la liste reste lisible dans les messages.
    return sorted(r for r in racines
                  if not any(r != autre and r.startswith(autre)
                             for autre in racines))


def agregats(conn: sqlite3.Connection, annee: int) -> dict:
    """Produits, charges hors dotations, dotation, résultat comptable, plafond 39C."""
    def somme(filtre, signe_debit=True):
        q = ("SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
             "JOIN ecriture e ON e.id=l.ecriture_id "
             "JOIN compte c ON c.numero=l.compte_num "
             f"WHERE e.exercice_annee=? AND {filtre}")
        v = conn.execute(q, (annee,)).fetchone()[0]
        return v if signe_debit else -v

    def somme_prefixes(prefixes, signe_debit=True):
        cond, args = _sql_prefixe("l.compte_num", prefixes)
        v = conn.execute(
            "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
            "JOIN ecriture e ON e.id=l.ecriture_id "
            f"WHERE e.exercice_annee=? AND {cond}", (annee, *args)).fetchone()[0]
        return v if signe_debit else -v

    cond_daa, args_daa = _sql_prefixe("l.compte_num", PREFIXE_DOTATION)
    produits = somme("c.classe=7", signe_debit=False)              # crédit - débit
    charges_hors_daa = conn.execute(
        "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "JOIN compte c ON c.numero=l.compte_num "
        f"WHERE e.exercice_annee=? AND c.classe=6 AND NOT {cond_daa}",
        (annee, *args_daa)).fetchone()[0]
    dotation = somme_prefixes(PREFIXE_DOTATION)
    resultat_comptable = round(produits - charges_hors_daa - dotation, 2)
    # Plafond 39 C = loyers acquis - charges AFFÉRENTES AU BIEN (art. 39 C,
    # II-2). Les charges de structure (honoraires comptables, CFE…) sont
    # exclues du calcul — voir comptes_hors_plafond_39c().
    exclus = racines_hors_plafond_39c(conn)
    hors_plafond = somme_prefixes(exclus) if exclus else 0.0
    produits_cession = somme_prefixes(PREFIXE_PRODUIT_CESSION, signe_debit=False)
    vnc_cession = somme_prefixes(PREFIXE_VNC_CESSION)
    # Les LOYERS ACQUIS : les produits de la location, à l'exclusion de ce
    # qui n'en est pas (financier, exceptionnel, reprises, transferts). La
    # base retranchait seulement le produit de cession d'un compte nommé,
    # et tout le reste de la classe 7 majorait le plafond.
    cond_hl, args_hl = _sql_prefixe("l.compte_num", PREFIXES_PRODUITS_HORS_LOYERS)
    produits_hors_loyers = -conn.execute(
        "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "JOIN compte c ON c.numero=l.compte_num "
        f"WHERE e.exercice_annee=? AND c.classe=7 AND {cond_hl}",
        (annee, *args_hl)).fetchone()[0]
    loyers_acquis = round(produits - produits_hors_loyers, 2)
    charges_afferentes = round(charges_hors_daa - hors_plafond, 2)
    plafond_39c = round(loyers_acquis - charges_afferentes, 2)
    return {"produits": round(produits, 2),
            "loyers_acquis": loyers_acquis,
            "produits_hors_loyers": round(produits_hors_loyers, 2),
            "charges_hors_daa": round(charges_hors_daa, 2),
            "charges_hors_plafond": round(hors_plafond, 2),
            "charges_afferentes": charges_afferentes,
            "dotation": round(dotation, 2),
            "resultat_comptable": resultat_comptable,
            "produits_cession": round(produits_cession, 2),
            "vnc_cession": round(vnc_cession, 2),
            "plafond_39c": plafond_39c}


# --- Moteur article 39 C ----------------------------------------------------

def calculer_39c(stock_ouverture: float, dotation: float, plafond: float) -> dict:
    """
    Applique la limitation 39 C pour un exercice.
    Part de dotation déductible = max(0, min(dotation, plafond)).
    - dotation > plafond  -> l'excédent (dotation - déductible) est REPORTÉ.
    - dotation <= plafond -> on peut DÉDUIRE une part du stock antérieur,
      dans la limite restante du plafond.
    Le report ne peut JAMAIS dépasser la dotation (cas plafond négatif).
    """
    deductible = max(0.0, min(dotation, plafond))
    report = round(dotation - deductible, 2)
    if report > TOL:
        utilisation = 0.0
    else:
        utilisation = round(max(0.0, min(stock_ouverture, plafond - dotation)), 2)
    stock_cloture = round(stock_ouverture + report - utilisation, 2)
    return {"stock_ouverture": round(stock_ouverture, 2), "dotation_exercice": round(dotation, 2),
            "plafond_deductible": round(plafond, 2), "report_annee": report,
            "utilisation_annee": utilisation, "stock_cloture": stock_cloture}


def _stock_39c_ouverture(conn: sqlite3.Connection, annee: int) -> float:
    """Stock d'amortissements reportés à l'ouverture de l'exercice.

    On lit le DERNIER exercice suivi antérieur, et non strictement N-1 :
    une série d'exercices n'est pas toujours contiguë. Un dossier repris
    depuis des FEC incomplets, ou une année sans activité qu'on n'a pas
    ouverte, laissait un trou — et la lecture stricte de N-1 ne trouvait
    rien, remettant le stock à ZÉRO. Le report, qui ne se périme jamais,
    disparaissait donc en silence, et le bénéfice de l'exercice suivant
    était déclaré en trop.

    C'était aussi une INCOHÉRENCE interne : la ventilation par bien lisait
    déjà le dernier exercice connu, si bien que la somme par bien cessait
    d'égaler le suivi global — l'invariant que le projet revendique.
    """
    row = conn.execute(
        "SELECT stock_cloture FROM suivi_39c WHERE exercice_annee < ? "
        "ORDER BY exercice_annee DESC LIMIT 1", (annee,)).fetchone()
    return row[0] if row else 0.0


def _annee_stock_ouverture(conn: sqlite3.Connection, annee: int) -> int | None:
    """L'exercice d'où provient le stock d'ouverture de `annee`."""
    row = conn.execute(
        "SELECT exercice_annee FROM suivi_39c WHERE exercice_annee < ? "
        "ORDER BY exercice_annee DESC LIMIT 1", (annee,)).fetchone()
    return row[0] if row else None


# --- Moteur déficits LMNP (FIFO, péremption 10 ans) -------------------------

def _table_suivi_deficits(conn):
    """Migration additive pour les dossiers existants, sans commit implicite."""
    conn.execute("CREATE TABLE IF NOT EXISTS suivi_deficits ("
                 "exercice_annee INTEGER PRIMARY KEY REFERENCES exercice(annee), "
                 "details_json TEXT NOT NULL)")


def traiter_deficit(conn: sqlite3.Connection, annee: int, resultat_fiscal: float,
                    commit: bool = True) -> dict:
    """
    Met à jour la file des déficits LMNP :
    - purge les déficits périmés (origine + 10 ans dépassés) ;
    - si déficit : crée un millésime (expiration = année + durée légale,
      règle versionnée 'duree_report_deficit_lmnp' — art. 156, I-1° ter CGI) ;
    - si bénéfice : impute sur les déficits les plus anciens non périmés (FIFO).

    `commit=False` : laisse la transaction ouverte (utilisé par `cloturer`,
    qui valide toute la clôture en un seul commit — la file des déficits
    n'étant pas idempotente, un commit intermédiaire suivi d'une interruption
    laisserait une imputation partielle rejouable).
    """
    duree = int(parametres.valeur(conn, "duree_report_deficit_lmnp",
                                  annee, defaut=10))
    import json

    _table_suivi_deficits(conn)
    if conn.execute("SELECT 1 FROM suivi_deficits WHERE exercice_annee=?",
                    (annee,)).fetchone():
        raise ValueError(f"Les déficits de {annee} ont déjà été traités.")
    cur = conn.cursor()
    ouverture = {r[0]: r[1] for r in cur.execute(
        "SELECT id, solde FROM deficit_lmnp WHERE annee_origine<=?", (annee,))}
    pertes = {}
    imputations = {}
    perimes = cur.execute("SELECT id, solde FROM deficit_lmnp "
                          "WHERE annee_expiration < ? AND solde > 0", (annee,)).fetchall()
    for did, perdu in perimes:
        pertes[did] = round(perdu, 2)
        cur.execute("UPDATE deficit_lmnp SET solde=0 WHERE id=?", (did,))

    impute = 0.0
    cree = None
    if resultat_fiscal < -TOL:                      # déficit de l'exercice
        montant = round(-resultat_fiscal, 2)
        cur.execute("INSERT INTO deficit_lmnp (annee_origine, montant_initial, solde, annee_expiration) "
                    "VALUES (?,?,?,?)", (annee, montant, montant, annee + duree))
        cree = montant
    elif resultat_fiscal > TOL:                     # bénéfice : imputation FIFO
        reste = round(resultat_fiscal, 2)
        for did, solde in cur.execute(
            "SELECT id, solde FROM deficit_lmnp WHERE solde>0 AND annee_expiration>=? "
            "AND annee_origine<? ORDER BY annee_origine, id", (annee, annee)).fetchall():
            if reste <= TOL:
                break
            pris = round(min(solde, reste), 2)
            cur.execute("UPDATE deficit_lmnp SET solde=ROUND(solde-?,2) WHERE id=?", (pris, did))
            reste = round(reste - pris, 2)
            impute += pris
            imputations[did] = pris

    # Instantané autonome : ne dépend ni des soldes futurs ni du montant
    # initial (qui peut déjà avoir été partiellement consommé à la reprise).
    details = []
    for did, origine, initial, solde, expiration in cur.execute(
            "SELECT id, annee_origine, montant_initial, solde, annee_expiration "
            "FROM deficit_lmnp WHERE annee_origine<=? ORDER BY annee_origine, id",
            (annee,)):
        details.append(dict(annee_origine=origine, montant_initial=round(initial, 2),
                            solde=round(solde, 2), annee_expiration=expiration,
                            solde_ouverture=round(ouverture.get(did, 0), 2),
                            impute=imputations.get(did, 0),
                            perte_peremption=pertes.get(did, 0)))
    cur.execute("INSERT INTO suivi_deficits VALUES (?, ?)",
                (annee, json.dumps(details)))
    if commit:
        conn.commit()
    total = cur.execute("SELECT COALESCE(SUM(solde),0) FROM deficit_lmnp").fetchone()[0]
    return {"perimes": len(perimes), "deficit_cree": cree,
            "impute_sur_benefice": round(impute, 2), "stock_deficits": round(total, 2)}


# --- Suivi 39 C par bien (ventilation du stock, logement par logement) ------
#
# Règle (liasses de référence § 4.1.2, art. 39 C) : « En présence de plusieurs
# logements, cette limitation est déterminée globalement pour chaque
# exploitant. Le suivi du stock d'amortissements encore reportables est par
# contre effectué logement par logement. »
# La LIMITATION reste donc globale (comportement validé par le test en or) ;
# seule la TENUE DU STOCK est ventilée ici :
#   - le report de l'année est réparti au prorata des dotations de chaque
#     bien (source : plan_amortissement × composant.bien_id) ;
#   - l'utilisation de l'année est répartie au prorata des stocks ;
#   - les arrondis sont ajustés sur la dernière ligne pour que la somme des
#     stocks par bien égale TOUJOURS le stock global, au centime.
# Activation « en cours de vie » : la table est créée à la volée ; un stock
# historique jamais ventilé est hérité par le bien le plus ancien (id min),
# ce qui est exact pour toute comptabilité restée mono-bien jusqu'ici.

def _table_39c_bien(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS suivi_39c_bien ("
        "  exercice_annee   INTEGER NOT NULL REFERENCES exercice(annee),"
        "  bien_id          INTEGER NOT NULL REFERENCES bien(id),"
        "  stock_ouverture  REAL NOT NULL DEFAULT 0,"
        "  dotation_bien    REAL NOT NULL DEFAULT 0,"
        "  report_bien      REAL NOT NULL DEFAULT 0,"
        "  utilisation_bien REAL NOT NULL DEFAULT 0,"
        "  sortie_bien      REAL NOT NULL DEFAULT 0,"
        "  stock_cloture    REAL NOT NULL DEFAULT 0,"
        "  PRIMARY KEY (exercice_annee, bien_id))")


def _repartir(total: float, poids: dict[int, float]) -> dict[int, float]:
    """Répartit `total` au prorata de `poids`, au centime, la somme des parts
    retombant EXACTEMENT sur le total — et aucune part négative.

    L'ajustement portait sur la DERNIÈRE part, à qui l'on donnait le reste :
    quand les arrondis des précédentes dépassaient déjà le total, ce reste
    était NÉGATIF. Sur quatre biens se partageant deux centimes, la dernière
    part valait −0,01 € — un mouvement de reprise négatif enregistré en
    base, et un centime de stock local en excès.

    On répartit donc par PLUS FORT RESTE : chaque part reçoit sa valeur
    tronquée au centime, puis les centimes encore à distribuer vont aux
    parts dont la décimale abandonnée était la plus grande. C'est la même
    règle que celle des répartitions de sièges, et elle ne peut pas rendre
    de part négative quand le total ne l'est pas.
    """
    if not poids or abs(total) < TOL:
        return dict.fromkeys(poids, 0.0)
    masse = sum(v for v in poids.values() if v > 0)
    if masse <= 0:                       # aucun poids : tout à la 1re clé
        parts = dict.fromkeys(poids, 0.0)
        parts[min(poids)] = round(total, 2)
        return parts
    if total < 0:                        # un total négatif garde l'ancienne
        cles = sorted(poids)             # règle : il n'a pas de « reste »
        parts = {b: round(total * max(poids[b], 0.0) / masse, 2)
                 for b in cles[:-1]}
        parts[cles[-1]] = round(total - sum(parts.values()), 2)
        return parts
    centimes_total = int(round(total * 100))
    exacts = {b: centimes_total * max(poids[b], 0.0) / masse for b in poids}
    parts_c = {b: int(v) for b, v in exacts.items()}
    reste = centimes_total - sum(parts_c.values())
    ordre = sorted(poids, key=lambda b: (-(exacts[b] - parts_c[b]), b))
    for b in ordre[:reste]:
        parts_c[b] += 1
    return {b: round(c / 100, 2) for b, c in parts_c.items()}


def _repartir_borne(total: float, poids: dict[int, float],
                    plafonds: dict[int, float]) -> dict[int, float]:
    """Comme `_repartir`, mais aucune part ne dépasse son plafond — et ce qui
    est ainsi écrêté est REDISTRIBUÉ sur celles qui ont encore de la place.

    L'utilisation du stock antérieur était répartie librement, puis chaque
    part était rabotée à ce que le bien possédait réellement. Le total
    reparti n'était alors plus le total global : les deux suivis, local et
    global, cessaient de concorder sans que rien ne le dise.
    """
    restant = round(total, 2)
    parts = dict.fromkeys(poids, 0.0)
    disponibles = dict(poids)
    for _ in range(len(poids) + 1):
        if restant <= TOL or not disponibles:
            break
        proposition = _repartir(restant, disponibles)
        bouge = False
        for b, p in proposition.items():
            place = round(plafonds.get(b, 0.0) - parts[b], 2)
            prise = round(min(p, max(0.0, place)), 2)
            if prise > 0:
                parts[b] = round(parts[b] + prise, 2)
                restant = round(restant - prise, 2)
                bouge = True
            if round(plafonds.get(b, 0.0) - parts[b], 2) <= TOL:
                disponibles.pop(b, None)
        if not bouge:
            break
    return parts


def _insuffisances_par_bien(conn: sqlite3.Connection, annee: int,
                            dotations: dict[int, float]) -> dict[int, float]:
    """Par bien : ce que sa dotation dépasse de sa marge locative.

    C'est cette insuffisance qui produit le report de l'article 39 C — la
    limitation s'apprécie bien par bien, même si le plafond se calcule
    globalement. Un bien dont les loyers couvrent sa dotation n'en produit
    aucun, et ne doit donc pas s'en voir attribuer.

    La marge se lit dans les OPÉRATIONS, seule couche qui rattache un
    montant à un bien. Un bien sans opération — historique repris depuis un
    FEC — n'a pas de marge connue : il rend une insuffisance nulle, et
    l'appelant retombe alors sur la répartition par dotations.
    """
    natures = {t: g.get("nature") for t, g in _g.tous(conn).items()}
    produits, charges = {}, {}
    try:
        import operations as _ops
        _ops.assurer_colonne_annulee(conn)
        lignes = conn.execute(
            "SELECT bien_id, type, COALESCE(SUM(montant),0) FROM operation "
            "WHERE exercice_annee=? AND COALESCE(annulee,0)=0 "
            "AND bien_id IS NOT NULL GROUP BY bien_id, type", (annee,))
    except sqlite3.Error:
        return dict.fromkeys(dotations, 0.0)
    for bien_id, type_op, montant in lignes:
        cible = produits if natures.get(type_op) == "produit" else charges
        cible[bien_id] = round(cible.get(bien_id, 0.0) + float(montant), 2)
    # Si AUCUN bien ne porte d'opération, la couche métier n'est pas tenue
    # dans ce dossier — un historique repris depuis un FEC, typiquement — et
    # aucune marge n'est connue de personne : l'appelant retombera sur les
    # dotations. Mais dès qu'elle est tenue, un bien sans opération a bien
    # une marge NULLE pour l'exercice ; lui prêter une insuffisance nulle
    # reviendrait à priver de report le seul bien qui n'a pas de loyer.
    if not produits and not charges:
        return dict.fromkeys(dotations, 0.0)
    out = {}
    for bien_id, dotation in dotations.items():
        marge = round(produits.get(bien_id, 0.0) - charges.get(bien_id, 0.0), 2)
        out[bien_id] = round(max(0.0, dotation - max(0.0, marge)), 2)
    return out


def _dotation_de_cession(conn: sqlite3.Connection, annee: int,
                         bien_id: int) -> float:
    """Dotation complémentaire passée à la cession de CE bien.

    Elle se reconnaît à la RÉFÉRENCE DE PIÈCE, qui porte l'identifiant du
    bien. L'ancien rattachement comparait le libellé des lignes au libellé
    des composants du bien : deux biens dont un composant porte le même nom
    — « Mobilier », disons — et chacun se voyait attribuer la dotation de
    l'autre, ce qui faussait toute la répartition du report.

    Les dossiers antérieurs à cette correction portent la pièce générique
    « DAA-CESSION » : on retombe alors sur l'ancien rattachement, mais
    restreint aux libellés qui n'appartiennent QU'À CE BIEN. Sur une
    collision de noms, il rend zéro plutôt qu'un multiple.
    """
    cond, args = _sql_prefixe("l.compte_num", PREFIXE_DOTATION)
    r = conn.execute(
        "SELECT COALESCE(ROUND(SUM(l.debit - l.credit), 2), 0) "
        "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
        f"WHERE e.exercice_annee = ? AND {cond} AND e.piece_ref = ?",
        (annee, *args, f"DAA-CESSION-{bien_id}")).fetchone()
    if r and r[0]:
        return float(r[0])
    r = conn.execute(
        "SELECT COALESCE(ROUND(SUM(l.debit - l.credit), 2), 0) "
        "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
        f"WHERE e.exercice_annee = ? AND {cond} AND e.piece_ref = 'DAA-CESSION' "
        "AND l.libelle IN (SELECT 'DAA cession - ' || c.libelle "
        "  FROM composant c WHERE c.bien_id = ? AND c.libelle NOT IN "
        "  (SELECT libelle FROM composant WHERE bien_id <> ?))",
        (annee, *args, bien_id, bien_id)).fetchone()
    return float(r[0]) if r and r[0] else 0.0


def _ventiler_39c_par_bien(conn: sqlite3.Connection, annee: int, s: dict) -> float:
    """Ventile le stock par bien. Retourne le total SORTI (ligne G' : stock
    39 C des biens cédés dans l'exercice, définitivement perdu — art. 39 C,
    le report n'est utilisable que tant que le bien est loué)."""
    _table_39c_bien(conn)
    try:
        conn.execute("ALTER TABLE suivi_39c_bien ADD COLUMN "
                     "sortie_bien REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass                              # colonne déjà présente
    biens = [r[0] for r in conn.execute("SELECT id FROM bien ORDER BY id")]
    if not biens:
        return 0.0                        # rien à ventiler (base sans bien)
    try:
        cedes = {r[0] for r in conn.execute(
            "SELECT id FROM bien WHERE date_cession IS NOT NULL AND "
            "date_cession < ?", (f"{annee + 1}-01-01",))}
    except sqlite3.OperationalError:
        cedes = set()                     # colonne absente : aucune cession
    # Le bien qui reçoit ce qu'on ne sait pas attribuer. C'était « le plus
    # ancien », sans égard pour sa cession : un dossier migré sans détail
    # historique voyait son stock global entier atterrir sur un bien DÉJÀ
    # SORTI, puis disparaître avec lui dès la clôture suivante — avec, au
    # passage, le report de l'exercice courant produit par le seul bien
    # encore actif. Un stock qu'on ne sait pas attribuer doit au moins
    # rester sur un bien qui existe encore.
    conserves = [b for b in biens if b not in cedes]
    refuge = conserves[0] if conserves else biens[0]

    # Dotations de l'exercice par bien (plan d'amortissement). À défaut
    # (reprise d'historique via rejeu FEC : dotation déjà dans les
    # écritures), la dotation globale est portée par le bien le plus ancien.
    dot = dict(conn.execute(
        "SELECT c.bien_id, ROUND(SUM(p.dotation),2) FROM plan_amortissement p "
        "JOIN composant c ON c.id=p.composant_id WHERE p.exercice_annee=? "
        "GROUP BY c.bien_id", (annee,)))
    # Un bien CÉDÉ en cours d'exercice a bien supporté une dotation — celle
    # passée à la cession — mais elle ne figure pas au plan d'amortissement
    # de clôture. Sans elle, il pesait ZÉRO dans la répartition du report,
    # si bien que la part qu'il aurait dû emporter dans sa sortie restait
    # attachée aux autres biens : le stock survivait à la disparition du
    # bien qui l'avait produit. On récupère donc sa dotation depuis les
    # ÉCRITURES de l'exercice (pièce « CESSION »).
    # La dotation de cession se rattache à SON bien. La requête d'origine
    # ne filtrait pas : chaque bien cédé recevait la SOMME des dotations de
    # tous les biens cédés de l'exercice, et pesait donc beaucoup trop dans
    # la répartition du report — au détriment des biens conservés, dont la
    # part de report se trouvait détruite avec les sortants.
    #
    # Le rattachement passe par l'ÉCRITURE : la dotation de cession et la
    # sortie d'actif du même bien appartiennent au même lot d'écritures,
    # et les lignes de sortie portent les comptes d'immobilisation de ses
    # composants. On remonte donc du compte au composant, puis au bien.
    for bien_id in cedes:
        if bien_id in dot:
            continue
        dotation_cession = _dotation_de_cession(conn, annee, bien_id)
        if dotation_cession:
            dot[bien_id] = dotation_cession
    if not dot:
        # Aucun plan pour l'exercice (reprise d'historique par rejeu FEC :
        # la dotation est déjà dans les écritures). On ne peut pas deviner
        # à quel bien elle revient — on la porte donc sur le bien refuge,
        # faute de mieux, et on le DIT plutôt que de le taire.
        #
        # Le refuge est un bien NON CÉDÉ. C'était « le plus ancien », si
        # bien qu'un dossier dont le premier bien avait été vendu voyait le
        # report de l'exercice — produit par le seul bien encore actif —
        # attribué au sortant, puis perdu avec lui dès cette clôture.
        dot = {refuge: s["dotation_exercice"]}

    # Stocks d'ouverture : la ventilation DU MÊME MILLÉSIME que le stock
    # global d'ouverture. Elle était lue sur le dernier exercice ventilé
    # quel qu'il soit : un détail de 2024 pouvait ainsi accompagner un
    # global de 2025, et les deux suivis présentaient des totaux différents
    # sans que rien ne le signale — 3 000 € sans propriétaire dans un cas
    # reproduit. Le détail d'une autre année n'est pas le détail de
    # celle-ci.
    annee_source = _annee_stock_ouverture(conn, annee)
    ouv = {}
    if annee_source is not None:
        ouv = dict(conn.execute(
            "SELECT bien_id, stock_cloture FROM suivi_39c_bien "
            "WHERE exercice_annee=?", (annee_source,)))
    ouv = {b: v for b, v in ouv.items() if abs(v) > TOL}
    # Ce qui reste sans propriétaire va au bien refuge, et l'invariant
    # « somme des stocks locaux = stock global » redevient vrai par
    # construction. Le contrôle `VENTILATION_39C` le dit à l'utilisateur :
    # cette affectation est un pis-aller, pas une donnée.
    ecart = round(s["stock_ouverture"] - sum(ouv.values()), 2)
    if abs(ecart) > TOL:
        ouv[refuge] = round(ouv.get(refuge, 0.0) + ecart, 2)

    # POIDS DU REPORT : l'INSUFFISANCE de chaque bien, et non sa dotation.
    # Le report naît des biens dont la dotation dépasse leur marge locative
    # (BOFiP, II, § 100) ; le répartir au prorata des dotations en donnait
    # une part à un bien qui couvrait la sienne par ses loyers. Cette part
    # partait ensuite avec lui à la cession, au détriment du bien qui
    # l'avait réellement produite. Faute de marge connue par bien — un
    # dossier repris d'un FEC n'a pas d'opérations —, on retombe sur les
    # dotations, comme avant.
    insuffisances = _insuffisances_par_bien(conn, annee, dot)
    poids_report = insuffisances if sum(insuffisances.values()) > TOL else dot

    reports = _repartir(s["report_annee"], poids_report)
    # L'utilisation ne peut pas excéder ce que chaque bien possède : elle
    # était répartie librement puis rabotée bien par bien, et le total
    # reparti cessait d'égaler le total global.
    capacites = {b: round(ouv.get(b, 0.0) + reports.get(b, 0.0), 2)
                 for b in set(ouv) | set(reports)}
    utilisations = _repartir_borne(s["utilisation_annee"], ouv, capacites)

    conn.execute("DELETE FROM suivi_39c_bien WHERE exercice_annee=?", (annee,))
    total_sorti = 0.0
    for b in sorted(set(biens) | set(ouv) | set(dot)):
        o = round(ouv.get(b, 0.0), 2)
        r = reports.get(b, 0.0)
        u = min(utilisations.get(b, 0.0), o + r)      # jamais plus que le stock
        restant = round(o + r - u, 2)
        sortie = 0.0
        if b in cedes and restant > 0:
            sortie, restant = restant, 0.0            # ligne G' : stock perdu
            total_sorti += sortie
        conn.execute(
            "INSERT INTO suivi_39c_bien (exercice_annee, bien_id, stock_ouverture,"
            " dotation_bien, report_bien, utilisation_bien, sortie_bien, "
            "stock_cloture) VALUES (?,?,?,?,?,?,?,?)",
            (annee, b, o, dot.get(b, 0.0), r, u, sortie, restant))
    return round(total_sorti, 2)


def suivi_39c_par_bien(conn: sqlite3.Connection, annee: int) -> list[dict]:
    """Ventilation du stock 39 C par bien pour l'exercice (liasse SUIV39C
    « logement par logement »). Liste vide si jamais ventilé."""
    _table_39c_bien(conn)
    return [dict(zip(("bien_id", "libelle", "stock_ouverture", "dotation_bien",
                      "report_bien", "utilisation_bien", "sortie_bien",
                      "stock_cloture"), r))
            for r in conn.execute(
                "SELECT v.bien_id, b.libelle, v.stock_ouverture, v.dotation_bien,"
                " v.report_bien, v.utilisation_bien, "
                "COALESCE(v.sortie_bien, 0), v.stock_cloture "
                "FROM suivi_39c_bien v JOIN bien b ON b.id=v.bien_id "
                "WHERE v.exercice_annee=? ORDER BY v.bien_id", (annee,))]


# --- Orchestration de clôture ----------------------------------------------

def _calcul_fiscal(conn: sqlite3.Connection, annee: int, ag: dict,
                   autres_retraitements: float = 0.0) -> dict:
    """
    Chaîne fiscale PURE : agrégats → plafond 39 C → résultat fiscal.
    N'écrit rien, ne décide rien du moment où on l'appelle.

    SOURCE UNIQUE de la règle. La clôture l'appelle pour figer le résultat ;
    la liasse provisoire l'appelle pour l'estimer. Les deux doivent tomber
    sur le même chiffre à partir des mêmes agrégats — recopier ce calcul
    ailleurs serait rouvrir la porte aux divergences.
    """
    stock_ouv = _stock_39c_ouverture(conn, annee)
    auto = round(retraitement_automatique(conn, annee), 2)
    autres = round(autres_retraitements + auto, 2)

    # Plafond EFFECTIF 39 C : les RÉINTÉGRATIONS (retraitements positifs) de
    # charges non déductibles afférentes au bien (fonds travaux ALUR…)
    # neutralisent ces charges — le plafond se calcule sur les charges
    # DÉDUCTIBLES afférentes au bien, il est donc majoré d'autant
    # (comportement vérifié contre les liasses réelles 2023-2025). Les
    # déductions extra-comptables (retraitements négatifs) ne modifient que
    # le résultat fiscal, jamais le plafond.
    # NOTE — une revue a proposé de n'y admettre que le retraitement
    # AUTOMATIQUE, au motif qu'un retraitement manuel portant sur une
    # charge NON afférente au bien (honoraires, CFE) majorerait le plafond
    # à tort. Le raisonnement est juste, mais la restriction a été REFUSÉE :
    # le test en or, calé sur trois liasses réelles, passe précisément
    # l'ALUR en retraitement manuel, et ces liasses montrent le plafond
    # majoré d'autant. Exclure le manuel aurait décalé les trois exercices
    # de 26, 57 et 61 €. Le logiciel ne peut pas savoir si un retraitement
    # saisi à la main est afférent au bien : c'est à l'utilisateur de le
    # dire, et un contrôle l'en avertit désormais.
    plafond_effectif = round(ag["plafond_39c"] + max(0.0, autres), 2)
    s = calculer_39c(stock_ouv, ag["dotation"], plafond_effectif)

    # Résultat fiscal = résultat comptable + report (réintégré) - utilisation
    #                   (déduite) + autres retraitements (fonds ALUR…)
    #                   + NEUTRALISATION de la cession : en LMNP, la plus ou
    #                   moins-value relève du régime des PARTICULIERS (art.
    #                   150 U CGI, déclarée par le notaire) — le produit
    #                   775000 est déduit du BIC, la VNC 675000 réintégrée.
    resultat_fiscal = round(ag["resultat_comptable"] + s["report_annee"]
                            - s["utilisation_annee"] + autres
                            + ag["vnc_cession"] - ag["produits_cession"], 2)
    return {"agregats": ag, "suivi_39c": s, "autres_retraitements": autres,
            "plafond_effectif": plafond_effectif,
            "resultat_fiscal": resultat_fiscal}


def simuler(conn: sqlite3.Connection, annee: int) -> dict:
    """
    Ce que DONNERAIT la clôture si elle avait lieu maintenant — sans rien
    écrire en base.

    Utile parce que la dotation aux amortissements n'est comptabilisée qu'à
    la clôture : sans simulation, la liasse provisoire affichait un résultat
    ignorant toute l'amortissement de l'année (et se contredisait, la 2033-C
    montrant une dotation que la 2033-B ne voyait pas).

    Renvoie en plus 'dotation_previsionnelle' : la dotation estimée d'après
    le plan, nulle si elle est déjà comptabilisée.
    """
    import amortissement
    ag = dict(agregats(conn, annee))
    deja = conn.execute(
        "SELECT 1 FROM ecriture WHERE exercice_annee=? AND journal_code='OD' "
        "AND piece_ref='DAA'", (annee,)).fetchone()
    previsionnelle = 0.0
    if deja is None:
        previsionnelle = round(sum(d["dotation"]
                                   for d in amortissement.dotations_exercice(
                                       conn, annee)), 2)
        ag["dotation"] = round(ag["dotation"] + previsionnelle, 2)
        ag["resultat_comptable"] = round(ag["resultat_comptable"]
                                         - previsionnelle, 2)
    calcul = _calcul_fiscal(conn, annee, ag)
    calcul["dotation_previsionnelle"] = previsionnelle
    return calcul


def retraitement_automatique(conn: sqlite3.Connection, annee: int) -> float:
    """
    Réintégration AUTOMATIQUE des opérations à retraitement fiscal (fonds de
    travaux ALUR : contribution capitalisée, non déductible —
    BOI-BIC-CHG-40-20). Activable, désactivable et datée par la règle
    versionnée 'retraitement_alur_auto'.

    SOURCE UNIQUE de la règle : la clôture l'applique pour figer le résultat
    fiscal, et la liasse PROVISOIRE l'applique pour ne pas afficher toute
    l'année un résultat fiscal qui ignore une charge non déductible déjà
    saisie. Les deux doivent répondre la même chose — d'où cette fonction
    plutôt qu'un calcul recopié.
    """
    if not parametres.valeur(conn, "retraitement_alur_auto", annee, defaut=1):
        return 0.0
    import operations as _ops
    _ops.assurer_colonne_annulee(conn)
    types_retr = [t for t, g in _g.tous(conn).items()
                  if g.get("retraitement") == "reintegration"]
    if not types_retr:
        return 0.0
    ph = ",".join("?" * len(types_retr))
    return round(conn.execute(
        f"SELECT COALESCE(SUM(montant),0) FROM operation "
        f"WHERE exercice_annee=? AND COALESCE(annulee,0)=0 "
        f"AND type IN ({ph})", (annee, *types_retr)).fetchone()[0], 2)


def cloturer(conn: sqlite3.Connection, annee: int, *, autres_retraitements: float = 0.0,
             generer_dotation: bool = True, forcer: bool = False) -> dict:
    """
    Clôture fiscale d'un exercice :
      1) génère la dotation aux amortissements (J4) si demandé ;
      2) calcule les agrégats et la limitation 39 C ;
      3) en déduit le résultat fiscal ;
      4) met à jour la file des déficits LMNP ;
      5) enregistre le suivi_39c et le résultat de l'exercice.

    Idempotence et atomicité : un exercice déjà clos est REFUSÉ (un re-POST
    du formulaire de clôture générait une seconde dotation DAA et une double
    imputation des déficits), et l'ensemble des étapes est validé par un
    commit UNIQUE en fin de fonction — une interruption en cours de clôture
    ne laisse aucun état intermédiaire en base.
    """
    # Verrou d'écriture AVANT le contrôle de statut : deux clôtures
    # simultanées (double-clic, deux onglets) passeraient sinon toutes deux
    # le contrôle « ouvert » puis généreraient chacune leur dotation. Avec
    # IMMEDIATE, la seconde attend la fin de la première et relit un statut
    # déjà « clos » → refus propre.
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    ex = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                      (annee,)).fetchone()
    if ex is None:
        raise ValueError(f"Exercice {annee} inexistant.")
    if ex[0] != "ouvert":
        raise ValueError(f"L'exercice {annee} est déjà clos — clôture refusée "
                         "(elle dupliquerait la dotation et l'imputation des "
                         "déficits).")
    # Ordre chronologique obligatoire : les reports (39 C, déficits) se
    # calculent d'année en année — clôturer N avant N-1 fausserait les
    # stocks d'ouverture de N.
    anterieur = conn.execute(
        "SELECT annee FROM exercice WHERE statut='ouvert' AND annee < ? "
        "ORDER BY annee LIMIT 1", (annee,)).fetchone()
    if anterieur:
        raise ValueError(f"Clôturez d'abord l'exercice {anterieur[0]} : les "
                         "clôtures se font dans l'ordre chronologique (les "
                         "reports d'amortissements et de déficits en dépendent).")
    # ... et l'ordre vaut AUSSI vers l'aval. La garde ci-dessus ne regardait
    # que les exercices antérieurs encore OUVERTS : rien n'empêchait
    # d'ajouter après coup un exercice ancien et de le clôturer alors que
    # les suivants étaient déjà clos. Or leur clôture a figé des stocks
    # d'ouverture calculés SANS ce déficit et SANS ce report : un bénéfice
    # de 600 € déjà déclaré imposable en N+1 aurait dû être absorbé par le
    # déficit que l'on vient de créer en N, et le stock de déficits compte
    # désormais 600 € de trop. Deux représentations incompatibles de la
    # même imputation coexistent, et rien ne les départage.
    #
    # Le logiciel ne peut pas recalculer les exercices postérieurs : ils
    # sont scellés, leur FEC est archivé, et leur liasse a pu être
    # déclarée. Il refuse donc, en disant ce qu'il faudrait faire.
    posterieur = conn.execute(
        "SELECT annee FROM exercice WHERE statut='clos' AND annee > ? "
        "ORDER BY annee LIMIT 1", (annee,)).fetchone()
    if posterieur:
        raise ValueError(
            f"L'exercice {posterieur[0]} est déjà clos : clôturer "
            f"{annee} maintenant fausserait ses reports. Sa clôture a figé "
            f"des stocks d'amortissements et de déficits calculés sans "
            f"{annee} ; les y faire entrer après coup demanderait de "
            f"reclôturer tous les exercices postérieurs, ce que leur "
            "scellement interdit. Restaurez une sauvegarde antérieure à la "
            f"clôture de {posterieur[0]}, puis reprenez les clôtures dans "
            "l'ordre chronologique.")

    # ANOMALIES BLOQUANTES. Le refus de clôturer sur un contrôle bloquant
    # était mis en œuvre par chaque interface — la route web et la CLI le
    # vérifiaient bien avant d'appeler ici — mais pas par la fonction qui
    # réalise la mutation IRRÉVERSIBLE. Un appel métier ordinaire figeait
    # donc 800 € de compte d'attente non identifiés sans rien demander. Une
    # garantie qui repose sur la discipline de ses appelants n'est pas une
    # garantie : elle vaut pour ceux qu'on connaît, et tombe au premier
    # nouvel appelant.
    #
    # `forcer=True` reste la dérogation EXPLICITE que les deux interfaces
    # proposent déjà par une case à cocher, et que les injections
    # volontaires des tests d'audit utilisent.
    if not forcer:
        import controles as _controles
        bloquantes = _controles.bloquants(_controles.controler(conn, annee))
        if bloquantes:
            details = " | ".join(f"{a.code} : {a.message}"
                                 for a in bloquantes[:3])
            raise ValueError(
                f"Clôture de {annee} refusée : {len(bloquantes)} anomalie(s) "
                f"bloquante(s). {details}"
                + (" …" if len(bloquantes) > 3 else "")
                + " Corrigez-les, ou clôturez en connaissance de cause "
                  "(option « Forcer »).")

    if generer_dotation:
        import amortissement
        amortissement.generer_cloture(conn, annee, commit=False)

    calcul = _calcul_fiscal(conn, annee, agregats(conn, annee),
                            autres_retraitements)
    ag = calcul["agregats"]
    autres_retraitements = calcul["autres_retraitements"]
    s = calcul["suivi_39c"]
    resultat_fiscal = calcul["resultat_fiscal"]

    # Ventilation par bien D'ABORD : elle détermine la ligne G' (stock 39 C
    # des biens cédés, définitivement perdu) qui vient RÉDUIRE le stock
    # global inscrit au suivi.
    sorties_39c = _ventiler_39c_par_bien(conn, annee, s)
    s["sorties_39c"] = sorties_39c
    s["stock_cloture"] = round(s["stock_cloture"] - sorties_39c, 2)
    conn.execute(
        "INSERT OR REPLACE INTO suivi_39c (exercice_annee, plafond_deductible, dotation_exercice, "
        "stock_ouverture, report_annee, utilisation_annee, stock_cloture) VALUES (?,?,?,?,?,?,?)",
        (annee, s["plafond_deductible"], s["dotation_exercice"], s["stock_ouverture"],
         s["report_annee"], s["utilisation_annee"], s["stock_cloture"]))

    defi = traiter_deficit(conn, annee, resultat_fiscal, commit=False)

    # Trace complète de la clôture (exploitée par la liasse fiscale).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cloture_fiscale ("
        "  exercice_annee   INTEGER PRIMARY KEY REFERENCES exercice(annee),"
        "  retraitements    REAL NOT NULL DEFAULT 0,"
        "  impute_deficits  REAL NOT NULL DEFAULT 0,"
        "  deficit_cree     REAL,"
        "  revenu_imposable REAL NOT NULL DEFAULT 0)")
    revenu_imposable = round(max(0.0, resultat_fiscal - defi["impute_sur_benefice"]), 2)
    conn.execute(
        "INSERT OR REPLACE INTO cloture_fiscale (exercice_annee, retraitements, "
        "impute_deficits, deficit_cree, revenu_imposable) VALUES (?,?,?,?,?)",
        (annee, round(autres_retraitements, 2), defi["impute_sur_benefice"],
         defi["deficit_cree"], revenu_imposable))

    conn.execute("UPDATE exercice SET statut='clos', resultat_comptable=?, resultat_fiscal=? "
                 "WHERE annee=?", (ag["resultat_comptable"], resultat_fiscal, annee))
    conn.commit()

    return {"agregats": ag, "suivi_39c": s, "resultat_fiscal": resultat_fiscal,
            "autres_retraitements": round(autres_retraitements, 2), "deficits": defi,
            "revenu_imposable": revenu_imposable}
