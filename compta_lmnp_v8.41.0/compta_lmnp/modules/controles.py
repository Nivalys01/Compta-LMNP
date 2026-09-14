# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Moteur de contrôles de cohérence — amorce.

Pendant « mou » du validateur FEC (qui, lui, est binaire et structurel) : ici on
produit des AVERTISSEMENTS à relever avant de figer la liasse, reproduisant la
logique des « Observations » des acteurs payants actuels. Trois niveaux : BLOQUANT, AVERTISSEMENT,
INFO.

Cette première salve couvre les familles directement observées dans tes liasses :
doublons, articles « Autres » à requalifier, dépenses immobilisables, complétude
des loyers, sens comptable, et équilibre par écriture.
"""
from __future__ import annotations
import sqlite3

import gabarits as _g
import amortissement
import parametres
from collections import defaultdict
from dataclasses import dataclass


BLOQUANT = "BLOQUANT"
AVERTISSEMENT = "AVERTISSEMENT"
INFO = "INFO"


@dataclass
class Anomalie:
    niveau: str
    code: str
    message: str


# --- Contrôles individuels --------------------------------------------------

def c_equilibre_ecritures(conn, annee) -> list[Anomalie]:
    """BLOQUANT — toute écriture doit être équilibrée."""
    rows = conn.execute(
        "SELECT e.ecriture_num, ROUND(SUM(l.debit),2), ROUND(SUM(l.credit),2) "
        "FROM ligne l JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=? GROUP BY e.ecriture_num", (annee,)
    ).fetchall()
    out = []
    for num, d, c in rows:
        if abs((d or 0) - (c or 0)) > 0.005:
            out.append(Anomalie(BLOQUANT, "EQUILIBRE",
                                f"Écriture {num} déséquilibrée : {d:.2f} ≠ {c:.2f}."))
    return out


def c_doublons(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — opérations de même type, même période, même montant."""
    rows = conn.execute(
        "SELECT type, periode, ROUND(montant,2), COUNT(*) "
        "FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? "
        "GROUP BY type, periode, ROUND(montant,2) HAVING COUNT(*) > 1", (annee,)
    ).fetchall()
    return [Anomalie(AVERTISSEMENT, "DOUBLON",
                     f"Doublon potentiel : {n}× '{t}' pour {per} à {m:.2f} €.")
            for t, per, m, n in rows]


def c_autres_a_requalifier(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — opérations tombées dans un compte 'fourre-tout'."""

    types = [t for t, g in _g.tous(conn).items() if g.get("requalifier")]
    if not types:
        return []
    ph = ",".join("?" * len(types))
    rows = conn.execute(
        f"SELECT id, periode, montant, libelle FROM operation "
        f"WHERE exercice_annee=? AND type IN ({ph})", (annee, *types)
    ).fetchall()
    return [Anomalie(AVERTISSEMENT, "REQUALIFIER",
                     f"Article « Autres » à valider (op. {oid}, {per}, {m:.2f} €) : "
                     f"« {lib} » — à reclasser dans un compte dédié.")
            for oid, per, m, lib in rows]


def c_depense_immobilisable(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — charge unitaire au-dessus du seuil d'immobilisation.
    Le seuil est une RÈGLE FISCALE VERSIONNÉE (menu Réglementation) : chaque
    exercice est contrôlé avec la valeur en vigueur à son millésime."""

    seuil_regle = parametres.valeur(conn, "seuil_immobilisation", annee, defaut=500.0)
    out = []
    for t, g in _g.tous(conn).items():
        if "seuil_immo" not in g:
            continue
        seuil = seuil_regle
        rows = conn.execute(
            "SELECT id, periode, montant FROM operation "
            "WHERE exercice_annee=? AND type=? AND montant > ?", (annee, t, seuil)
        ).fetchall()
        out += [Anomalie(AVERTISSEMENT, "IMMOBILISABLE",
                         f"Dépense potentiellement immobilisable (op. {oid}, {per}) : "
                         f"{m:.2f} € > seuil {seuil:.0f} € — charge ou immobilisation ?")
                for oid, per, m in rows]
    return out


def c_completude_loyers(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — 12 loyers mensuels attendus ; signale les mois manquants."""
    present = {r[0] for r in conn.execute(
        "SELECT periode FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? AND type='loyer'", (annee,)
    ) if r[0]}
    attendus = {f"{annee}-{m:02d}" for m in range(1, 13)}
    manquants = sorted(attendus - present)
    if not present:
        return []   # aucune saisie de loyer encore : on ne signale rien
    if manquants:
        return [Anomalie(AVERTISSEMENT, "LOYER_MANQUANT",
                         f"Loyers manquants ({len(manquants)} mois) : {', '.join(manquants)}.")]
    return []


def c_sens_comptable(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — charge au crédit ou produit au débit (hors annulation)."""
    rows = conn.execute(
        "SELECT e.ecriture_num, l.compte_num, c.classe, l.debit, l.credit "
        "FROM ligne l JOIN ecriture e ON e.id=l.ecriture_id "
        "JOIN compte c ON c.numero=l.compte_num "
        "WHERE e.exercice_annee=? AND e.journal_code='BQ'", (annee,)
    ).fetchall()
    out = []
    for num, compte, classe, d, cr in rows:
        if classe == 6 and (cr or 0) > 0.005:
            out.append(Anomalie(AVERTISSEMENT, "SENS",
                                f"Écriture {num} : charge {compte} au crédit ({cr:.2f}) — annulation ?"))
        if classe == 7 and (d or 0) > 0.005:
            out.append(Anomalie(AVERTISSEMENT, "SENS",
                                f"Écriture {num} : produit {compte} au débit ({d:.2f}) — annulation ?"))
    return out


# --- Seconde salve : structurels bloquants ----------------------------------

def c_dates_hors_exercice(conn, annee) -> list[Anomalie]:
    """BLOQUANT — écriture datée hors des bornes de l'exercice (FEC invalide)."""
    ex = conn.execute("SELECT date_debut, date_fin FROM exercice WHERE annee=?",
                      (annee,)).fetchone()
    if not ex:
        return []
    rows = conn.execute(
        "SELECT ecriture_num, ecriture_date FROM ecriture "
        "WHERE exercice_annee=? AND (ecriture_date < ? OR ecriture_date > ?)",
        (annee, ex[0], ex[1])).fetchall()
    return [Anomalie(BLOQUANT, "DATE_HORS_EXERCICE",
                     f"Écriture {num} datée du {d}, hors exercice "
                     f"[{ex[0]} → {ex[1]}].") for num, d in rows]


def c_compte_attente(conn, annee) -> list[Anomalie]:
    """BLOQUANT — solde non nul sur 472000 (à-nouveaux en attente) : à apurer
    avant clôture, sinon le bilan est faux."""
    s = conn.execute(
        "SELECT ROUND(SUM(l.debit - l.credit),2) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=? AND l.compte_num='472000'", (annee,)
    ).fetchone()[0]
    if s and abs(s) > 0.005:
        return [Anomalie(BLOQUANT, "COMPTE_ATTENTE",
                         f"Compte d'attente 472000 non soldé : {s:.2f} € — "
                         "reclasser avant la clôture.")]
    return []


def c_montants_invalides(conn, annee) -> list[Anomalie]:
    """BLOQUANT — opération à montant nul ou négatif (import corrompu)."""
    rows = conn.execute(
        "SELECT id, type, montant FROM operation "
        "WHERE exercice_annee=? AND montant <= 0", (annee,)).fetchall()
    return [Anomalie(BLOQUANT, "MONTANT_INVALIDE",
                     f"Opération {oid} ({t}) : montant {m:.2f} € ≤ 0.")
            for oid, t, m in rows]


# --- Seconde salve : plausibilité et périodicité -----------------------------

def c_duree_allongee(conn, annee) -> list[Anomalie]:
    """
    AVERTISSEMENT — le cumul comptabilisé dépasse le plan théorique, signe
    d'une durée d'amortissement ALLONGÉE après coup.

    L'article 39 B du CGI impose un amortissement minimum : à la clôture de
    chaque exercice, la somme des amortissements pratiqués depuis la mise
    en service ne peut être inférieure au cumul linéaire calculé sur la
    durée retenue à l'origine. Allonger la durée réduit l'annuité, fait
    décrocher le cumul de ce minimum, et l'écart constitue un
    amortissement IRRÉGULIÈREMENT DIFFÉRÉ — définitivement perdu, à la
    différence du report de l'article 39 C.

    Une exception mérite d'être connue, et le message la rappelle : si la
    durée avait été RÉDUITE auparavant pour un motif particulier
    (obsolescence prévue, sinistre) et que ce motif a disparu, revenir à
    une durée plus longue est légitime. Le logiciel ne peut pas trancher —
    il signale.

    Le logiciel ne conservant pas la durée d'origine, l'allongement se
    déduit de sa SIGNATURE : le cumul réellement en compte dépasse ce que
    le plan actuel prévoyait à l'ouverture de l'exercice.
    """
    import amortissement as _am
    out = []
    # `date_sortie` n'existe que sur les bases ayant connu une cession
    # (cession.assurer_schema la crée) : on filtre donc les biens cédés à
    # part, plutôt que d'imposer une migration à tous les dossiers.
    try:
        rows = conn.execute(
            "SELECT id, libelle, valeur_brute, duree_annees, "
            "date_mise_service, compte_amort, bien_id FROM composant "
            "WHERE amortissable=1").fetchall()
    except sqlite3.OperationalError:
        return []
    try:
        cedes = {r[0] for r in conn.execute(
            "SELECT id FROM bien WHERE date_cession IS NOT NULL")}
    except sqlite3.OperationalError:
        cedes = set()
    for cid, lib, vb, duree, dms, c_amort, bien_id in rows:
        if not duree or not c_amort or bien_id in cedes:
            continue
        deja = _am._cumul_comptabilise(conn, cid, c_amort, annee)
        if deja is None:                 # compte partagé : indécidable
            continue
        try:
            _, cumul_prevu, _ = _am.etat(vb, duree, dms, annee - 1)
        except Exception:                # noqa: BLE001
            continue
        ecart = round(deja - cumul_prevu, 2)
        if ecart <= max(1.0, 0.01 * float(vb)):
            continue
        out.append(Anomalie(AVERTISSEMENT, "DUREE_ALLONGEE",
            f"« {lib} » : {deja:.2f} € d'amortissements sont comptabilisés, "
            f"alors que le plan actuel n'en prévoyait que {cumul_prevu:.2f} € "
            f"à l'ouverture de {annee} ({ecart:+.2f} €). La durée a "
            "probablement été ALLONGÉE après coup. L'article 39 B du CGI "
            "impose un amortissement minimum linéaire calculé sur la durée "
            "retenue à l'origine : allonger la durée fait décrocher le "
            "cumul de ce minimum, et l'écart est définitivement perdu — il "
            "ne se reporte pas, à la différence de l'article 39 C. "
            "L'allongement n'est admis que s'il ramène à la durée normale "
            "une durée précédemment RÉDUITE pour un motif particulier "
            "(obsolescence prévue, sinistre) désormais disparu. Sinon, "
            "revenez à la durée d'origine."))
    return out


def c_retraitement_manuel_majore_le_plafond(conn, annee) -> list[Anomalie]:
    """
    AVERTISSEMENT — un retraitement saisi à la main majore le plafond 39 C.

    Un retraitement positif neutralise une charge comptabilisée mais non
    déductible ; quand cette charge est AFFÉRENTE AU BIEN — le fonds de
    travaux ALUR, cas d'école —, le plafond d'amortissement déductible est
    légitimement majoré d'autant, et c'est ce que montrent les liasses
    réelles qui servent d'étalon au projet.

    Mais le logiciel ne peut pas savoir si la charge retraitée est
    afférente au bien. Si elle ne l'est pas — honoraires comptables, CFE,
    que le calcul du plafond exclut justement —, la majoration est
    indue et fait déduire plus d'amortissement que l'article 39 C ne
    l'autorise. Signalé plutôt que deviné.
    """
    try:
        r = conn.execute(
            "SELECT COALESCE(retraitements, 0) FROM cloture_fiscale "
            "WHERE exercice_annee=?", (annee,)).fetchone()
    except sqlite3.OperationalError:
        return []
    total = float(r[0]) if r else 0.0
    if total <= 0.5:
        return []
    auto = 0.0
    try:
        import fiscal as _fiscal
        auto = round(_fiscal.retraitement_automatique(conn, annee), 2)
    except Exception:                            # noqa: BLE001
        return []
    manuel = round(total - auto, 2)
    if manuel <= 0.5:
        return []
    return [Anomalie(AVERTISSEMENT, "RETRAITEMENT_MANUEL_PLAFOND",
            f"{manuel:.2f} € de retraitement ont été saisis à la main, en "
            f"plus des {auto:.2f} € réintégrés automatiquement. Ce montant "
            "majore aussi le PLAFOND d'amortissement déductible (art. 39 C) "
            "— ce qui est correct si la charge retraitée est afférente au "
            "bien loué (fonds de travaux ALUR), mais indu s'il s'agit d'une "
            "charge de structure (honoraires comptables, CFE). Vérifiez ce "
            "point : dans le second cas, vous déduiriez plus "
            "d'amortissement que la loi ne l'autorise.")]


def c_deficit_menace_par_le_39c(conn, annee) -> list[Anomalie]:
    """
    AVERTISSEMENT — un déficit près d'expirer n'a pas pu s'imputer parce
    que le report d'amortissement a absorbé le bénéfice avant lui.

    Les deux reports n'ont PAS la même durée de vie : les amortissements
    reportés au titre de l'article 39 C s'imputent sans limite de temps,
    tandis qu'un déficit LMNP se périme dix ans après sa naissance. Quand
    le bénéfice ne suffit pas à absorber les deux, l'ordre décide donc de
    ce qui sera perdu — et le logiciel impute le 39 C en premier, par
    construction : sa reprise entre dans le calcul du résultat fiscal, sur
    lequel les déficits s'imputent ensuite.

    Le logiciel ne CHANGE PAS cet ordre de lui-même : savoir si la reprise
    du 39 C peut être différée à volonté est une question qui se discute,
    et la trancher en silence dans un sens favorable serait exactement le
    genre de décision qu'un logiciel ne doit pas prendre à la place de son
    utilisateur. Il signale la situation, chiffrée, pour que celui-ci
    puisse la porter à un professionnel.
    """
    # Sur un exercice OUVERT, la table de suivi n'existe pas encore : le
    # contrôle se taisait donc jusqu'à la clôture — c'est-à-dire jusqu'au
    # moment où il n'est plus temps d'agir. Or le rapport de contrôles se
    # lit AVANT de figer la liasse, et `fiscal.simuler()` connaît déjà la
    # reprise qui sera faite. On l'interroge quand la table est muette.
    try:
        ligne = conn.execute(
            "SELECT COALESCE(utilisation_annee, 0) FROM suivi_39c "
            "WHERE exercice_annee=?", (annee,)).fetchone()
    except sqlite3.OperationalError:
        # Robustesse : cette première requête n'était pas protégée alors
        # que la seconde l'était. Sur une base sans la table, c'est tout
        # `controler()` qui tombait.
        ligne = None
    utilise_39c = ligne[0] if ligne else 0
    if not utilise_39c:
        try:
            import fiscal as _fiscal
            projection = _fiscal.simuler(conn, annee)
            utilise_39c = projection["suivi_39c"]["utilisation_annee"]
        except Exception:                       # noqa: BLE001
            utilise_39c = 0
    if not utilise_39c or utilise_39c < 1:
        return []
    try:
        menaces = conn.execute(
            "SELECT annee_origine, solde, annee_expiration FROM deficit_lmnp "
            "WHERE solde > 1 AND annee_expiration IS NOT NULL "
            "AND annee_expiration - ? <= 3 ORDER BY annee_expiration",
            (annee,)).fetchall()
    except sqlite3.OperationalError:
        return []
    if not menaces:
        return []
    total = round(sum(m[1] for m in menaces), 2)
    detail = ", ".join(f"{m[1]:.2f} € né en {m[0]} (expire fin {m[2]})"
                       for m in menaces[:3])
    return [Anomalie(AVERTISSEMENT, "DEFICIT_MENACE_PAR_39C",
            f"{utilise_39c:.2f} € d'amortissements reportés ont été repris "
            f"cette année, alors que {total:.2f} € de déficits approchent de "
            f"leur péremption ({detail}). Les deux reports n'ont pas la même "
            "durée de vie : le report d'amortissement (art. 39 C) s'impute "
            "sans limite de temps, un déficit LMNP se périme à dix ans. "
            "Si le bénéfice ne suffit pas à absorber les deux, c'est le "
            "déficit qui se perd. Ce point mérite d'être posé à un "
            "professionnel avant le dépôt.")]


def c_postes_habituels_absents(conn, annee) -> list[Anomalie]:
    """
    INFO — postes que presque tout dossier LMNP comporte, et qui manquent.

    Le contrôle de plausibilité compare à l'an dernier : sur un dossier
    NEUF il n'a rien à comparer et se tait. L'utilisateur d'un premier
    exercice n'était donc averti de rien, alors que c'est lui qui a le
    plus besoin d'une liste (retour d'usage). Ce contrôle-ci ne regarde
    que l'exercice courant, et ne parle que de postes quasi certains.
    """
    saisies = conn.execute(
        "SELECT COUNT(*) FROM operation WHERE exercice_annee=? "
        "AND COALESCE(annulee,0)=0", (annee,)).fetchone()[0]
    if saisies < 3:
        return []          # dossier à peine commencé : rien à reprocher
    presents = {r[0] for r in conn.execute(
        "SELECT DISTINCT type FROM operation WHERE exercice_annee=? "
        "AND COALESCE(annulee,0)=0", (annee,))}

    attendus = [
        ("interets_emprunt",
         "Aucun intérêt d'emprunt",
         "Si le bien a été financé à crédit, les intérêts et l'assurance "
         "emprunteur sont déductibles — c'est souvent le poste de charge "
         "le plus élevé. Ignorez si l'achat était comptant."),
        ("assurance",
         "Aucune assurance",
         "L'assurance propriétaire non occupant (PNO) est due, et souvent "
         "prélevée automatiquement : elle passe alors inaperçue."),
        ("taxe_fonciere",
         "Aucune taxe foncière",
         "Elle est due chaque année par le propriétaire. Pensez aussi à "
         "la TEOM, sur le même avis."),
        ("cfe",
         "Aucune CFE",
         "La cotisation foncière des entreprises s'applique à la location "
         "meublée, sauf exonération, et n'est généralement pas due la "
         "première année."),
        ("charge_copro",
         "Aucune charge de copropriété",
         "Si le bien est en copropriété, les appels de charges sont "
         "déductibles — ventilez-les depuis la page Saisie."),
    ]
    out = []
    for type_op, titre, pourquoi in attendus:
        if type_op in presents:
            continue
        out.append(Anomalie(INFO, "POSTE_HABITUEL_ABSENT",
                   f"{titre} sur {annee}. {pourquoi}"))
    return out


def c_plausibilite_n1(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — total d'un type variant fortement vs N-1 (>50 % et
    >100 €). Ne joue que si l'exercice précédent est clos."""
    # Une année à peine ouverte n'a rien à comparer : au 2 janvier, TOUTES
    # les charges de l'an dernier sont « manquantes ». Signaler cela
    # reviendrait à noyer l'utilisateur d'alertes chaque début d'exercice —
    # et c'est exactement ce qui arrivait sur le dossier de démonstration,
    # dont l'exercice courant ne porte que ses à-nouveaux.
    saisies = conn.execute(
        "SELECT COUNT(*) FROM operation WHERE exercice_annee=? "
        "AND COALESCE(annulee,0)=0", (annee,)).fetchone()[0]
    if saisies < 3:
        return []
    prec = conn.execute("SELECT 1 FROM exercice WHERE annee=? AND statut='clos'",
                        (annee - 1,)).fetchone()
    if not prec:
        return []
    # Exercice précédent migré par FEC (à-nouveaux seuls, pas d'opérations) :
    # comparer à zéro serait du bruit, on passe.
    n_ops_n1 = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=?",
                            (annee - 1,)).fetchone()[0]
    if n_ops_n1 == 0:
        return []
    q = ("SELECT type, ROUND(SUM(montant),2) FROM operation "
         "WHERE exercice_annee=? GROUP BY type")
    n  = dict(conn.execute(q, (annee,)).fetchall())
    n1 = dict(conn.execute(q, (annee - 1,)).fetchall())
    out = []
    for t in sorted(set(n) | set(n1)):
        a, b = n.get(t, 0.0), n1.get(t, 0.0)
        ecart = abs(a - b)
        base = max(abs(b), 1.0)
        if ecart > 100.0 and ecart / base > 0.5:
            out.append(Anomalie(AVERTISSEMENT, "PLAUSIBILITE_N1",
                f"'{t}' : {a:.2f} € en {annee} vs {b:.2f} € en {annee-1} "
                f"({'+' if a>b else '−'}{ecart:.0f} €) — évolution à justifier."))
    return out


def c_loyer_atypique(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — loyer mensuel s'écartant de plus de 15 % de la médiane
    annuelle (erreur de saisie ou changement de loyer à documenter)."""
    rows = [r[0] for r in conn.execute(
        "SELECT montant FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? AND type='loyer' "
        "ORDER BY montant", (annee,)).fetchall()]
    if len(rows) < 3:
        return []
    mediane = rows[len(rows) // 2]
    out = []
    for per, m in conn.execute(
        "SELECT periode, montant FROM operation "
        "WHERE exercice_annee=? AND type='loyer'", (annee,)).fetchall():
        if mediane > 0 and abs(m - mediane) / mediane > 0.15 and abs(m - mediane) > 20:
            out.append(Anomalie(AVERTISSEMENT, "LOYER_ATYPIQUE",
                f"Loyer {per} : {m:.2f} € vs médiane annuelle {mediane:.2f} € — "
                "erreur de saisie ou changement de loyer ?"))
    return out


def c_annuel_multiple(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — un type à périodicité ANNUELLE saisi plusieurs fois
    (CFE ×2, deux taxes foncières…)."""

    annuels = [t for t, g in _g.tous(conn).items()
               if g.get("periodicite") == "annuel"]
    if not annuels:
        return []
    ph = ",".join("?" * len(annuels))
    rows = conn.execute(
        f"SELECT type, COUNT(*) FROM operation "
        f"WHERE exercice_annee=? AND type IN ({ph}) "
        f"GROUP BY type HAVING COUNT(*) > 1", (annee, *annuels)).fetchall()
    return [Anomalie(AVERTISSEMENT, "ANNUEL_MULTIPLE",
                     f"'{t}' (périodicité annuelle) saisi {n} fois — doublon "
                     "ou rattrapage à documenter.") for t, n in rows]


def c_periode_incoherente(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — période déclarée ≠ mois de la date d'opération."""
    rows = conn.execute(
        "SELECT id, type, periode, date_operation FROM operation "
        "WHERE exercice_annee=? AND periode IS NOT NULL "
        "AND periode <> SUBSTR(date_operation,1,7)", (annee,)).fetchall()
    return [Anomalie(AVERTISSEMENT, "PERIODE_INCOHERENTE",
                     f"Opération {oid} ({t}) : période {per} ≠ mois de la date "
                     f"{d} — décalage volontaire (rattrapage) ou erreur ?")
            for oid, t, per, d in rows]


def c_an_absents(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — l'exercice précédent est clos mais aucun à-nouveau
    n'a été repris : le bilan de l'exercice sera faux."""
    prec = conn.execute("SELECT 1 FROM exercice WHERE annee=? AND statut='clos'",
                        (annee - 1,)).fetchone()
    if not prec:
        return []
    an = conn.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=? "
                      "AND journal_code='AN'", (annee,)).fetchone()[0]
    if an == 0:
        return [Anomalie(AVERTISSEMENT, "AN_ABSENTS",
                f"L'exercice {annee-1} est clos mais {annee} n'a pas d'à-nouveaux : "
                "reprenez le bilan (Nouvel exercice → reprise) sinon le 2033-A sera faux.")]
    return []


def c_dotation_vs_plan(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — dotation comptabilisée (681120) ≠ plan d'amortissement
    théorique. Ne joue que si une dotation a été passée."""
    # La dotation de CESSION est passée hors clôture et n'apparaît pas au
    # plan théorique, qui exclut les composants sortis. La compter ici
    # garantissait un écart — donc un avertissement alarmant et faux à
    # CHAQUE cession, égal au montant de cette dotation.
    comptab = conn.execute(
        "SELECT ROUND(SUM(l.debit),2) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=? AND l.compte_num='681120' "
        "AND COALESCE(l.libelle,'') NOT LIKE 'DAA cession%'", (annee,)
    ).fetchone()[0] or 0.0
    if comptab < 0.005:
        return []
    theorique = round(sum(d["dotation"] for d in
                          amortissement.dotations_exercice(conn, annee)), 2)
    if abs(comptab - theorique) > 0.01:
        return [Anomalie(AVERTISSEMENT, "DOTATION_PLAN",
                f"Dotation comptabilisée {comptab:.2f} € ≠ plan théorique "
                f"{theorique:.2f} € — dotation en double ou composant modifié "
                "après clôture ?")]
    return []


def c_seuil_lmp(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — recettes au-dessus du seuil LMP (règle versionnée) :
    le statut LMNP peut basculer, à vérifier au niveau du foyer."""
    seuil = parametres.valeur(conn, "seuil_lmp_recettes", annee, defaut=23000.0)

    produits = [t for t, g in _g.tous(conn).items() if g["nature"] == "produit"]
    ph = ",".join("?" * len(produits))
    ca = conn.execute(
        f"SELECT ROUND(COALESCE(SUM(montant),0),2) FROM operation "
        f"WHERE exercice_annee=? AND type IN ({ph})", (annee, *produits)
    ).fetchone()[0]
    if ca > seuil:
        return [Anomalie(AVERTISSEMENT, "SEUIL_LMP",
                f"Recettes {ca:.2f} € > seuil LMP {seuil:.0f} € (art. 155 IV CGI) : "
                "vérifier le critère de prépondérance au niveau du foyer — "
                "le statut LMP changerait le régime des déficits et plus-values.")]
    return []


def c_interets_mal_classes(conn, annee) -> list[Anomalie]:
    """AVERTISSEMENT — libellé évoquant un emprunt saisi ailleurs qu'en
    charges financières (cas réel constaté : intérêts en « frais de tenue de
    compte » et « autres charges » dans les exercices 2023-2025)."""
    rows = conn.execute(
        "SELECT id, type, montant, libelle FROM operation "
        "WHERE exercice_annee=? AND type NOT IN "
        "('interets_emprunt','assurance_emprunteur','frais_dossier_emprunt') "
        "AND (LOWER(COALESCE(libelle,'')) LIKE '%intér%' "
        "  OR LOWER(COALESCE(libelle,'')) LIKE '%interet%' "
        "  OR LOWER(COALESCE(libelle,'')) LIKE '%emprunt%' "
        "  OR LOWER(COALESCE(libelle,'')) LIKE '%échéance%')", (annee,)
    ).fetchall()
    return [Anomalie(AVERTISSEMENT, "INTERETS_MAL_CLASSES",
                     f"Opération {oid} ({t}, {m:.2f} €) : « {lib} » — des intérêts "
                     "d'emprunt ? Utiliser le gabarit dédié (compte 661100, "
                     "ligne 294 du 2033-B).") for oid, t, m, lib in rows]


# --- Seconde salve : charges attendues (INFO) --------------------------------

def c_charges_attendues(conn, annee) -> list[Anomalie]:
    """INFO — charges quasi certaines absentes alors que l'activité tourne
    (loyers présents) : taxe foncière, CFE, assurance. Rappels de fin d'année."""
    loyers = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? "
                          "AND type='loyer'", (annee,)).fetchone()[0]
    if loyers < 6:
        return []
    attendues = [
        (("taxe_fonciere", "impot_local", "teom"), "taxe foncière / TEOM"),
        (("cfe",), "CFE"),
        (("assurance", "assurance_emprunteur", "assurance_gli"), "assurance PNO"),
    ]
    out = []
    for types, lib in attendues:
        ph = ",".join("?" * len(types))
        n = conn.execute(f"SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? "
                         f"AND type IN ({ph})", (annee, *types)).fetchone()[0]
        if n == 0:
            out.append(Anomalie(INFO, "CHARGE_ATTENDUE",
                       f"Aucune {lib} saisie sur {annee} — oubli probable "
                       "(charge quasi certaine en location meublée)."))
    return out


def c_alur_absent(conn, annee) -> list[Anomalie]:
    """INFO — copropriété présente et fonds ALUR saisi en N-1 mais absent
    en N : la contribution est en général appelée chaque trimestre."""
    copro = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? "
                         "AND type='charge_copro'", (annee,)).fetchone()[0]
    alur_n = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? "
                          "AND type='fonds_travaux_alur'", (annee,)).fetchone()[0]
    alur_n1 = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 AND exercice_annee=? "
                           "AND type='fonds_travaux_alur'", (annee - 1,)).fetchone()[0]
    if copro > 0 and alur_n == 0 and alur_n1 > 0:
        return [Anomalie(INFO, "ALUR_ABSENT",
                f"Fonds travaux ALUR saisi en {annee-1} mais absent en {annee} "
                "malgré des charges de copropriété — vérifier la ventilation "
                "des appels (le fonds est réintégré fiscalement, pas déductible).")]
    return []


def c_amortissements_anterieurs(conn, annee) -> list[Anomalie]:
    """
    AVERTISSEMENT — bien entré dans le logiciel alors qu'il était déjà
    amorti depuis des années, sans reprise du cumul antérieur.

    Constaté sur un dossier réel : l'écriture d'entrée portait la valeur
    brute (117 000 €) sans le cumul d'amortissement déjà couru depuis
    2021 (≈ 9 879 €). Le tableau 2033-C, qui déroule le plan depuis la
    mise en service, affichait donc 12 219 € d'amortissements quand le
    bilan n'en connaissait que 2 340 — un écart qui ne se résorbe jamais
    de lui-même et qui fausse la valeur nette comptable, donc la
    plus-value en cas de revente.
    """
    import operations as _ops
    try:
        m = _ops.amortissements_anterieurs_manquants(conn, annee)
    except Exception:
        return []
    if not m["par_compte"]:
        return []
    noms = ", ".join(d["composant"] for d in m["detail"][:3])
    return [Anomalie(AVERTISSEMENT, "AMORT_ANTERIEURS",
            f"{m['total']:.2f} € d'amortissements déjà courus avant "
            f"{annee} ne sont pas comptabilisés ({noms}). Le bilan "
            "présente le bien comme neuf alors que le tableau 2033-C "
            "déroule son plan depuis la mise en service : l'écart "
            "apparaîtra à chaque liasse. Corrigez-le en un clic depuis "
            "la page Immobilisations (« Reprendre les amortissements "
            "antérieurs ») — le résultat de l'exercice n'en est pas "
            "affecté, seul le bilan est remis à l'endroit.")]


def c_ventilation_incoherente(conn, annee) -> list[Anomalie]:
    """
    AVERTISSEMENT — somme des composants éloignée du prix d'acquisition.

    On pouvait empiler des composants sans qu'aucun lien ne soit fait avec
    le prix payé. Deux dérives symétriques : sur-ventiler (on amortit plus
    que ce qu'on a payé — redressement assuré) ou sous-ventiler (une part
    du prix n'est jamais amortie, avantage perdu).

    Seule la SOUS-ventilation est signalée en permanence. Un dépassement,
    lui, devient normal dès que des travaux sont immobilisés — et le reste
    définitivement : en faire une alerte permanente reviendrait à crier sur
    tout dossier un peu vivant. Le dépassement est donc signalé au moment
    où il se produit (à la ventilation initiale et à l'ajout d'un
    composant), pas à chaque contrôle.
    """
    del annee
    out = []
    for bien_id, lib, prix in conn.execute(
            "SELECT id, libelle, prix_total FROM bien"):
        if not prix:
            continue
        total = conn.execute(
            "SELECT COALESCE(SUM(valeur_brute),0) FROM composant "
            "WHERE bien_id=?", (bien_id,)).fetchone()[0]
        if not total:
            continue
        manquant = round(prix - total, 2)
        if manquant <= 0.05 * prix:
            continue
        out.append(Anomalie(AVERTISSEMENT, "VENTILATION_INCOMPLETE",
                   f"Bien « {lib} » : la somme des composants "
                   f"({total:.2f} €) reste inférieure de {manquant:.2f} € "
                   f"({manquant / prix * 100:.1f} %) au prix d'acquisition "
                   f"({prix:.2f} €). Cette part n'est donc jamais amortie : "
                   "vérifiez qu'aucun poste n'a été oublié (agencements, "
                   "mobilier, installations techniques). C'est un avantage "
                   "fiscal perdu, silencieusement, chaque année."))
    return out


def c_composant_non_amortissable(conn, annee) -> list[Anomalie]:
    """
    BLOQUANT — composant portant une durée d'amortissement alors que son
    compte n'a pas de contrepartie (terrain).

    Découvert en usage : la saisie était acceptée, puis la clôture échouait
    sur « NOT NULL constraint failed: ligne.compte_num ». Le contrôle
    pré-clôture doit le dire AVANT, en langage compréhensible.
    """
    del annee
    mauvais = conn.execute(
        "SELECT libelle, compte_immo FROM composant "
        "WHERE amortissable=1 AND (compte_amort IS NULL OR compte_amort='')"
    ).fetchall()
    return [Anomalie(BLOQUANT, "COMPOSANT_SANS_AMORT",
            f"Composant « {lib} » (compte {cpt}) : une durée "
            "d'amortissement est renseignée mais ce compte ne s'amortit "
            "pas — un terrain ne se déprécie pas. Mettez sa durée à 0 dans "
            "la page Immobilisations, sinon la clôture échouera.")
            for lib, cpt in mauvais]


def c_teom_oubliee(conn, annee) -> list[Anomalie]:
    """
    INFO — taxe foncière saisie sans TEOM.

    L'avis de taxe foncière porte les deux : la taxe elle-même et la
    taxe d'enlèvement des ordures ménagères, qui se récupère sur le
    locataire. Saisir l'une sans l'autre est l'oubli le plus courant du
    dépouillement de l'avis.
    """
    tf = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 "
                      "AND exercice_annee=? AND type='taxe_fonciere'",
                      (annee,)).fetchone()[0]
    if not tf:
        return []
    teom = conn.execute("SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 "
                        "AND exercice_annee=? AND type='teom'",
                        (annee,)).fetchone()[0]
    if teom:
        return []
    return [Anomalie(INFO, "TEOM_ABSENTE",
            "Taxe foncière saisie sans TEOM : l'avis porte les deux. La "
            "taxe d'enlèvement des ordures ménagères se saisit à part "
            "(elle se récupère sur le locataire) — vérifiez votre avis.")]


CONTROLES = [
    # structurels (bloquants)
    c_equilibre_ecritures,
    c_dates_hors_exercice,
    c_compte_attente,
    c_montants_invalides,
    # qualité de saisie
    c_doublons,
    c_autres_a_requalifier,
    c_depense_immobilisable,
    c_completude_loyers,
    c_sens_comptable,
    c_annuel_multiple,
    c_periode_incoherente,
    c_interets_mal_classes,
    # plausibilité et cohérence fiscale
    c_plausibilite_n1,
    c_postes_habituels_absents,
    c_deficit_menace_par_le_39c,
    c_retraitement_manuel_majore_le_plafond,
    c_duree_allongee,
    c_loyer_atypique,
    c_an_absents,
    c_dotation_vs_plan,
    c_amortissements_anterieurs,
    c_composant_non_amortissable,
    c_ventilation_incoherente,
    c_teom_oubliee,
    c_seuil_lmp,
    # rappels (info)
    c_charges_attendues,
    c_alur_absent,
]


def controler(conn: sqlite3.Connection, annee: int) -> list[Anomalie]:
    """Exécute tous les contrôles et renvoie la liste agrégée des anomalies."""
    import operations as _ops
    _ops.assurer_colonne_annulee(conn)
    anomalies: list[Anomalie] = []
    for ctl in CONTROLES:
        anomalies += ctl(conn, annee)
    ordre = {BLOQUANT: 0, AVERTISSEMENT: 1, INFO: 2}
    return sorted(anomalies, key=lambda a: ordre[a.niveau])


def rapport(conn: sqlite3.Connection, annee: int) -> str:
    """Rapport texte lisible, à consulter avant de figer la liasse."""
    anos = controler(conn, annee)
    if not anos:
        return f"Contrôles {annee} : aucune anomalie. ✓"
    par_niveau = defaultdict(int)
    lignes = [f"Contrôles de cohérence {annee} :"]
    for a in anos:
        par_niveau[a.niveau] += 1
        lignes.append(f"  [{a.niveau:<13}] {a.code:<13} {a.message}")
    resume = ", ".join(f"{n} {niv.lower()}(s)" for niv, n in par_niveau.items())
    lignes.append(f"\nBilan : {resume}.")
    if par_niveau[BLOQUANT]:
        lignes.append("⛔ Des anomalies BLOQUANTES empêchent la clôture.")
    return "\n".join(lignes)


def bloquants(anos: list[Anomalie]) -> list[Anomalie]:
    return [a for a in anos if a.niveau == BLOQUANT]
