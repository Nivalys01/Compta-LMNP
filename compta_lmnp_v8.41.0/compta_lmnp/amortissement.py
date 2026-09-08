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


def plan(valeur_brute: float, duree_annees: int, date_mise_service: str) -> list[tuple[int, float]]:
    """Déroule le plan : liste de (année, dotation) de la mise en service à l'épuisement."""
    valeur = _d(valeur_brute)
    annuelle = _q(valeur / _d(duree_annees))
    an0 = int(date_mise_service[:4])

    out: list[tuple[int, float]] = []
    cumul = _d("0")
    annee = an0
    premier = True
    while cumul < valeur:
        if premier:
            dot = _q(annuelle * fraction_prorata(date_mise_service))
            premier = False
        else:
            dot = annuelle
        if cumul + dot > valeur:           # plafond dernière année
            dot = valeur - cumul
        out.append((annee, float(dot)))
        cumul += dot
        annee += 1
        if len(out) > duree_annees + 2:    # garde-fou anti-boucle
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


def dotations_exercice(conn: sqlite3.Connection, annee: int) -> list[dict]:
    """Dotation de l'exercice par composant amortissable (dotation > 0 uniquement)."""
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
    out = []
    for cid, lib, vb, duree, dms, c_amort, bien_id in rows:
        dot, cumul, vnc = etat(vb, duree, dms, annee)
        # BORNE SUR LE DÉJÀ COMPTABILISÉ. `etat()` recalcule le plan à
        # neuf depuis la mise en service : si la durée du composant est
        # modifiée après coup — un allongement, une correction de saisie —
        # le cumul théorique de l'exercice peut se retrouver INFÉRIEUR à ce
        # qui a réellement été passé les années précédentes, et la dotation
        # proposée ne tient aucun compte de cet historique. Sur une durée
        # portée de 5 à 8 ans après trois exercices, le plan reprenait à
        # 1 000 €/an alors que 4 800 € étaient déjà comptabilisés : le
        # total aurait dépassé la valeur brute.
        #
        # La dotation ne peut donc jamais excéder ce qu'il RESTE à amortir,
        # c'est-à-dire la valeur brute moins le cumul déjà écrit en compte.
        deja = _cumul_comptabilise(conn, cid, c_amort, annee)
        if deja is not None:
            reste = round(float(vb) - deja, 2)
            if reste <= 0.005:
                continue                     # composant déjà intégralement amorti
            if dot > reste:
                dot = reste
                cumul = round(float(vb), 2)
                vnc = 0.0
        if dot > 0.005:
            out.append({"composant_id": cid, "libelle": lib, "compte_amort": c_amort,
                        "bien_id": bien_id, "dotation": dot, "cumul_fin": cumul, "vnc_fin": vnc})
    return out


def _cumul_comptabilise(conn: sqlite3.Connection, composant_id: int,
                        compte_amort: str | None, annee: int) -> float | None:
    """Cumul d'amortissement RÉELLEMENT écrit en compte avant l'exercice.

    Renvoie None quand la lecture n'est pas possible (base incomplète) :
    on retombe alors sur le plan théorique, comportement d'origine.

    Le compte d'amortissement peut être partagé par plusieurs composants
    (plusieurs bâtiments sur 281315). Dans ce cas on ne peut pas isoler la
    part d'un composant : on ne borne rien, plutôt que de borner à tort.
    """
    if not compte_amort:
        return None
    try:
        partage = conn.execute(
            "SELECT COUNT(*) FROM composant WHERE compte_amort=? "
            "AND amortissable=1", (compte_amort,)).fetchone()[0]
        if partage != 1:
            return None
        # Le solde se lit sur le DERNIER exercice antérieur, et sur lui
        # seul. Additionner tous les exercices doublerait le cumul : les
        # à-nouveaux de chaque année reportent déjà le solde de la
        # précédente — le piège classique de ce schéma.
        # Exercice CLOS uniquement : un exercice ouvert n'a pas encore
        # reçu sa dotation, et borner sur son solde partiel laisserait
        # passer une dotation qui aurait dû être plafonnée.
        prec = conn.execute(
            "SELECT MAX(e.exercice_annee) FROM ecriture e "
            "JOIN exercice x ON x.annee = e.exercice_annee "
            "WHERE e.exercice_annee < ? AND x.statut = 'clos'",
            (annee,)).fetchone()[0]
        if prec is None:
            return 0.0
        r = conn.execute(
            "SELECT COALESCE(ROUND(SUM(l.credit - l.debit), 2), 0) FROM ligne l "
            "JOIN ecriture e ON e.id = l.ecriture_id "
            "WHERE l.compte_num = ? AND e.exercice_annee = ?",
            (compte_amort, prec)).fetchone()
        return float(r[0]) if r else None
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
    if quote_part_terrain and 0 < quote_part_terrain <= 1:
        reste = 1 - quote_part_terrain
        autres = sum(x["part"] for x in lignes if x["cle"] != "terrain")
        for x in lignes:
            x["part"] = (quote_part_terrain if x["cle"] == "terrain"
                         else round(x["part"] / autres * reste, 4)
                         if autres else 0.0)
    for x in lignes:
        x["montant"] = round(prix_total * x["part"], 2)
    # L'arrondi ne doit pas faire perdre ou inventer des euros.
    ecart = round(prix_total - sum(x["montant"] for x in lignes), 2)
    if ecart:
        cible = max(lignes, key=lambda x: x["montant"])
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
    deja = conn.execute(
        "SELECT ecriture_num FROM ecriture WHERE exercice_annee=? "
        "AND journal_code='OD' AND piece_ref='DAA'", (annee,)).fetchone()
    if deja is not None:
        raise ValueError(f"Dotation aux amortissements déjà générée pour "
                         f"{annee} (écriture OD n°{deja[0]}).")
    date_cloture = date_cloture or f"{annee}-12-31"
    dotations = dotations_exercice(conn, annee)
    if not dotations:
        return {"ecriture_id": None, "total": 0.0, "nb_composants": 0}

    # Garde-fou : un composant amortissable sans compte d'amortissement
    # produisait une ligne à compte NULL, donc une IntegrityError SQLite
    # illisible en pleine clôture. On nomme le coupable et le geste.
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
