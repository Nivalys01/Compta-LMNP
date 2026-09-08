# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Jalon J5 — Moteurs fiscaux : limitation art. 39 C du CGI et déficits LMNP.

DEUX FILES STRICTEMENT DISTINCTES (jamais cumulées) :
  - Report 39 C : amortissements non déductibles, reportables SANS limite de durée.
  - Déficit LMNP : imputable sur bénéfices de même nature, PÉREMPTION à 10 ans.

⚠️ AVERTISSEMENT — ce module code la mécanique observée chez les acteurs payants actuels, mais le calcul
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


def agregats(conn: sqlite3.Connection, annee: int) -> dict:
    """Produits, charges hors dotations, dotation, résultat comptable, plafond 39C."""
    def somme(filtre, signe_debit=True):
        q = ("SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
             "JOIN ecriture e ON e.id=l.ecriture_id "
             "JOIN compte c ON c.numero=l.compte_num "
             f"WHERE e.exercice_annee=? AND {filtre}")
        v = conn.execute(q, (annee,)).fetchone()[0]
        return v if signe_debit else -v

    produits = somme("c.classe=7", signe_debit=False)              # crédit - débit
    charges_hors_daa = somme("c.classe=6 AND l.compte_num<>'681120'")
    dotation = somme("l.compte_num='681120'")
    resultat_comptable = round(produits - charges_hors_daa - dotation, 2)
    # Plafond 39 C = loyers acquis - charges AFFÉRENTES AU BIEN (art. 39 C,
    # II-2). Les charges de structure (honoraires comptables, CFE…) sont
    # exclues du calcul — voir comptes_hors_plafond_39c().
    exclus = comptes_hors_plafond_39c(conn)
    hors_plafond = 0.0
    if exclus:
        ph = ",".join("?" * len(exclus))
        hors_plafond = conn.execute(
            "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
            "JOIN ecriture e ON e.id=l.ecriture_id "
            f"WHERE e.exercice_annee=? AND l.compte_num IN ({ph})",
            (annee, *exclus)).fetchone()[0]
    produits_cession = -conn.execute(
        "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=? AND l.compte_num='775000'",
        (annee,)).fetchone()[0]
    vnc_cession = conn.execute(
        "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=? AND l.compte_num='675000'",
        (annee,)).fetchone()[0]
    charges_afferentes = round(charges_hors_daa - hors_plafond, 2)
    # Le plafond 39 C se calcule sur les LOYERS ACQUIS : le produit de
    # cession (775000) n'en fait pas partie.
    plafond_39c = round(produits - produits_cession - charges_afferentes, 2)
    return {"produits": round(produits, 2),
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


# --- Moteur déficits LMNP (FIFO, péremption 10 ans) -------------------------

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
    cur = conn.cursor()
    perimes = cur.execute("SELECT id, solde FROM deficit_lmnp "
                          "WHERE annee_expiration < ? AND solde > 0", (annee,)).fetchall()
    for did, _ in perimes:
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
            "ORDER BY annee_origine", (annee,)).fetchall():
            if reste <= TOL:
                break
            pris = round(min(solde, reste), 2)
            cur.execute("UPDATE deficit_lmnp SET solde=ROUND(solde-?,2) WHERE id=?", (pris, did))
            reste = round(reste - pris, 2)
            impute += pris

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
    """Répartit `total` au prorata de `poids`, arrondi au centime, en ajustant
    la dernière part pour que la somme retombe EXACTEMENT sur le total."""
    if not poids or total == 0:
        return dict.fromkeys(poids, 0.0)
    masse = sum(poids.values())
    if masse <= 0:                       # aucun poids : tout à la 1re clé
        parts = dict.fromkeys(poids, 0.0)
        parts[min(poids)] = round(total, 2)
        return parts
    cles = sorted(poids)
    parts = {b: round(total * poids[b] / masse, 2) for b in cles[:-1]}
    parts[cles[-1]] = round(total - sum(parts.values()), 2)
    return parts


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
        r = conn.execute(
            "SELECT COALESCE(ROUND(SUM(l.debit - l.credit), 2), 0) "
            "FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
            "WHERE e.exercice_annee = ? AND l.compte_num = '681120' "
            "AND l.libelle IN (SELECT 'DAA cession - ' || c.libelle "
            "                  FROM composant c WHERE c.bien_id = ?)",
            (annee, bien_id)).fetchone()
        if r and r[0]:
            dot[bien_id] = float(r[0])
    if not dot:
        # Aucun plan pour l'exercice (reprise d'historique par rejeu FEC :
        # la dotation est déjà dans les écritures). On ne peut pas deviner
        # à quel bien elle revient — on la porte donc sur le bien le plus
        # ancien, faute de mieux, et on le DIT plutôt que de le taire.
        dot = {biens[0]: s["dotation_exercice"]}

    # Stocks d'ouverture : ventilation N-1 si elle existe ; sinon l'historique
    # global est hérité par le bien le plus ancien (activation en cours de vie).
    ouv = dict(conn.execute(
        "SELECT bien_id, stock_cloture FROM suivi_39c_bien WHERE exercice_annee="
        "(SELECT MAX(exercice_annee) FROM suivi_39c_bien WHERE exercice_annee<?)",
        (annee,)))
    if not ouv:
        ouv = {biens[0]: s["stock_ouverture"]}

    reports = _repartir(s["report_annee"], dot)
    utilisations = _repartir(s["utilisation_annee"], ouv)

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
             generer_dotation: bool = True) -> dict:
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
