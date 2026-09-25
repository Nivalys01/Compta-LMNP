# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Emprunts — tableau de remboursement et génération des échéances.

LA BANQUE FAIT FOI. Le calcul propose un tableau ; l'utilisateur le
remplace ligne à ligne ou importe celui de la banque ; le logiciel contrôle
la cohérence de ce qui est saisi (invariants ci-dessous). Validé contre le
tableau d'une offre réelle (prêt amortissable à taux fixe, 228 échéances
constantes après un différé) : échéance, dernière ligne ajustée et totaux
annuels de capital et d'intérêts identiques au centime.

Ce qui est comptabilisé (choix du dossier, décision du 25/09/2026) : les
seules CHARGES de l'échéance, en une écriture de banque —
  661100 « Intérêts des emprunts » (PCG 6611 « Intérêts des emprunts et
         dettes » ; ligne 294 du 2033-B)  débit  intérêts
  616110 « Primes assurances » (PCG 616)   débit  assurance emprunteur
  108000 « Exploitant »                    crédit total
Sources : CGI, art. 39-1 et BOI-BIC-CHG-50, § 1 et § 10 (les intérêts
bancaires sont des charges financières déductibles) ; règlement ANC
n° 2014-03, plan de comptes de l'art. 1121-1 (932-1 avant 2025) pour les
comptes 164, 275, 616 et 661 ; Code de la consommation, art. L313-25, 3°
(échéancier capital / intérêts joint à l'offre à taux fixe) et L314-1
(le TAEG ajoute les frais aux intérêts). En cas de conflit, le PCG et le
CGI priment. Toutes figurent au corpus de la Veille fiscale. Le CAPITAL n'est pas comptabilisé : son remboursement éteint une
dette, ce n'est pas une charge, et le bilan simplifié du logiciel ne
porte pas de dettes (liasse.bilan_2033a).

Déblocages successifs : tant que les fonds se débloquent par tranches,
les intérêts se saisissent à la main ; le tableau se décrit (ou
s'importe) à partir de l'échéance où le prêt suit son cours normal, et
seules ses échéances se génèrent. Les contrôles ne comparent que cette
période. Le tableau garde capital et capital
restant dû (CRD) pour le suivi ; les contrôles le confrontent au compte
164000 lorsque le dossier en porte un (FEC de cabinet repris).

Calcul — prêt amortissable à échéances constantes (lot 1) :
  - taux périodique PROPORTIONNEL : i = taux nominal annuel × mois / 12.
    Taux NOMINAL (taux débiteur), pas le TAEG, qui ajoute les frais et
    l'assurance et ne sert qu'à comparer des offres ;
  - échéance hors assurance : C × i / (1 − (1 + i)^−n), au centime
    (ROUND_HALF_UP) — formule de l'annuité constante ; taux nul : C / n ;
  - par ligne : intérêts = CRD × i au centime, capital = échéance −
    intérêts ; la dernière ligne amortit le CRD exact ;
  - Decimal de bout en bout (puissance comprise), montants stockés en
    centimes entiers : aucun float avant le guichet.

Invariants (création, remplacement, import) : Σ capital = CRD de départ au
centime, CRD final nul, aucun montant négatif, CRD de chaque ligne = CRD
précédent − capital, dates strictement croissantes, CRD strictement
décroissant pour une ligne calculée et jamais croissant (un report, une
capitalisation d'intérêts, est une erreur).

Hors lot 1 (première échéance brisée, différé, taux variable, modulation,
remboursement anticipé, in fine, déblocages successifs) : on remplace les
lignes concernées par celles de la banque.
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

import echeancier

SOURCE = "emprunt"
PERIODICITES = {"mensuelle": 1, "trimestrielle": 3, "annuelle": 12}
DUREE_MAX = 480                       # 40 ans de mensualités
# Borne de vraisemblance du taux nominal (décision du 25/09/2026). Au-delà,
# c'est une virgule décalée (35 pour 3,5) ou un TAEG, pas un taux de prêt
# immobilier : refus avec un message qui le dit.
TAUX_MAX = Decimal("0.20")
CENTIME = Decimal("0.01")
LONGUEUR_TEXTE = 120
# Seuil des contrôles : le CRD et les intérêts se connaissent au centime,
# le seul seuil absolu de matérialité s'applique (décision du 25/09/2026).
SEUIL_ECART = Decimal("5.00")

AIDE_TAUX = ("Taux NOMINAL annuel (taux débiteur) indiqué dans l'offre, pas "
             "le TAEG : le TAEG ajoute aux intérêts les frais, l'assurance et "
             "les garanties (Code de la consommation, art. L314-1) ; il sert "
             "à comparer des offres, pas à calculer les intérêts d'une "
             "échéance.")
AIDE_DEBLOCAGES = (
    "Déblocages successifs : tant que les fonds se débloquent par tranches, "
    "saisissez les intérêts à la main (page Saisie, « Intérêts "
    "d'emprunt »). Décrivez l'emprunt, puis importez le tableau de la "
    "banque à partir de l'échéance où le prêt suit son cours normal : "
    "seules ces échéances seront générées, et les contrôles ne comparent "
    "que cette période.")
RAPPEL_CHARGES = ("Seules les parts intérêts et assurance d'une échéance sont "
                  "des charges déductibles. Le remboursement du capital n'en "
                  "est pas une : il n'est pas comptabilisé, le tableau le "
                  "suit pour information.")


# ── Montants, taux, dates ────────────────────────────────────────────────

def arrondi(x: Decimal) -> Decimal:
    return x.quantize(CENTIME, rounding=ROUND_HALF_UP)


def en_centimes(x: Decimal) -> int:
    return int(arrondi(x) * 100)


def en_euros(c: int) -> Decimal:
    return (Decimal(int(c)) / 100).quantize(CENTIME)


_MONTANT_SIMPLE = re.compile(r"^-?\d+(?:[.,]\d{1,2})?$")
_MONTANT_MILLIERS = re.compile(r"^-?\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?$")


def lire_montant(texte, quoi: str = "montant") -> Decimal:
    """Montant écrit par un humain ou une banque, lu STRICTEMENT.

    Admis : « 1234,56 », « 1234.56 », « 1 234,56 » (espace, insécable ou
    fine insécable entre milliers), signe moins, symbole € final. Refusés
    plutôt que devinés : un nombre portant à la fois « . » et « , »
    (« 1.234,56 » ou « 1,234.56 » selon le pays), plus de deux décimales,
    et un seul séparateur suivi de trois chiffres (« 1,234 » : mille deux
    cent trente-quatre, ou un virgule deux cent trente-quatre ?).
    Le signe est conservé : un montant négatif n'est jamais retourné.
    """
    if isinstance(texte, Decimal):
        return texte
    if isinstance(texte, int):
        return Decimal(texte)
    if isinstance(texte, float):
        # Un float ne se lit pas au centime près : il passe par sa
        # représentation décimale la plus courte, comme l'écrirait un humain.
        texte = repr(texte)
    s = str(texte or "").strip()
    for espace in (" ", " "):
        s = s.replace(espace, " ")
    if s.endswith("€"):
        s = s[:-1].strip()
    if not s:
        raise ValueError(f"{quoi} : valeur vide.")
    if "." in s and "," in s:
        raise ValueError(f"{quoi} « {texte} » : « . » et « , » dans le même "
                         "nombre — séparateur décimal ambigu, refusé plutôt "
                         "que deviné. Écrivez 1234,56.")
    if re.fullmatch(r"-?\d{1,3}[.,]\d{3}", s):
        raise ValueError(f"{quoi} « {texte} » : séparateur ambigu (milliers "
                         "ou décimales ?). Écrivez 1234 ou 1,23.")
    if not (_MONTANT_SIMPLE.match(s) or _MONTANT_MILLIERS.match(s)):
        raise ValueError(f"{quoi} « {texte} » illisible (au plus deux "
                         "décimales ; milliers séparés par une espace).")
    return Decimal(s.replace(" ", "").replace(",", "."))


def lire_taux(texte) -> Decimal:
    """Taux nominal saisi EN POURCENTAGE (« 3,5 » → 0,035)."""
    if isinstance(texte, Decimal):
        return texte
    s = str(texte or "").strip().rstrip("%").strip().replace(",", ".")
    try:
        taux = Decimal(s) / 100
    except InvalidOperation:
        raise ValueError(f"Taux nominal « {texte} » illisible (exemple : "
                         "3,5 pour 3,5 %).") from None
    if not taux.is_finite():
        raise ValueError(f"Taux nominal « {texte} » illisible.")
    return taux


_FORMATS_DATE = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


def lire_date(texte, quoi: str = "date") -> date:
    """Date stricte : un 31 février est REFUSÉ, jamais reporté au 3 mars."""
    if isinstance(texte, date):
        return texte
    s = str(texte or "").strip()
    for fmt in _FORMATS_DATE:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{quoi} « {texte} » invalide (date inexistante, ou "
                     "format autre que JJ/MM/AAAA ou AAAA-MM-JJ).")


def _texte(valeur, quoi: str, requis: bool = False) -> str | None:
    s = (valeur or "").strip()
    if not s:
        if requis:
            raise ValueError(f"{quoi} : champ obligatoire.")
        return None
    if any(c in s for c in "\t\r\n"):
        raise ValueError(f"{quoi} : une seule ligne, sans tabulation "
                         "(le texte passe dans le libellé des écritures).")
    if len(s) > LONGUEUR_TEXTE:
        raise ValueError(f"{quoi} : {LONGUEUR_TEXTE} caractères au plus.")
    return s


def euros_fr(x: Decimal) -> str:
    """1234.5 → « 1 234,50 » (affichage)."""
    signe = "-" if x < 0 else ""
    ent, dec = f"{abs(x):.2f}".split(".")
    groupes = []
    while ent:
        groupes.insert(0, ent[-3:])
        ent = ent[:-3]
    return f"{signe}{' '.join(groupes)},{dec}"


def taux_fr(taux: Decimal) -> str:
    """0.0125 → « 1,25 » ; 0.01 → « 1 » (affichage, sans arrondi)."""
    t = format((taux * 100).normalize(), "f")
    return t.replace(".", ",")


# ── Calcul (fonctions pures) ─────────────────────────────────────────────

@dataclass
class LigneTableau:
    rang: int
    date: date
    capital: Decimal
    interets: Decimal
    assurance: Decimal
    crd: Decimal                  # capital restant dû APRÈS l'échéance
    origine: str = "calcul"       # calcul | saisie | import

    @property
    def echeance(self) -> Decimal:
        """Échéance hors assurance."""
        return self.capital + self.interets

    @property
    def total(self) -> Decimal:
        """Montant prélevé, assurance comprise."""
        return self.capital + self.interets + self.assurance


def taux_periodique(taux: Decimal, periodicite: str) -> Decimal:
    """i = taux annuel × (mois de la période / 12) — taux proportionnel."""
    return taux * PERIODICITES[periodicite] / 12


def echeance_constante(crd: Decimal, i: Decimal, n: int) -> Decimal:
    """C × i / (1 − (1 + i)^−n) au centime ; C / n à taux nul."""
    with localcontext() as ctx:
        ctx.prec = 34
        if i == 0:
            return arrondi(crd / n)
        return arrondi(crd * i / (1 - (1 + i) ** -n))


def amortir(crd: Decimal, i: Decimal, dates: list[date],
            assurances: list[Decimal], premier_rang: int) -> list[LigneTableau]:
    """Tableau à échéances constantes de `crd` sur len(dates) échéances."""
    n = len(dates)
    a = echeance_constante(crd, i, n)
    out = []
    for k, (jour, assurance) in enumerate(zip(dates, assurances)):
        with localcontext() as ctx:
            ctx.prec = 34
            interets = arrondi(crd * i)
        capital = crd if k == n - 1 else a - interets
        crd = crd - capital
        out.append(LigneTableau(premier_rang + k, jour, capital, interets,
                                assurance, crd))
    return out


def dates_echeances(premiere: date, periodicite: str, n: int,
                    premier_rang: int = 1) -> list[date]:
    """Jour de la première échéance tenu, borné au dernier jour du mois."""
    pas = PERIODICITES[periodicite]
    return [echeancier.date_ancree(premiere, pas, r - 1)
            for r in range(premier_rang, premier_rang + n)]


def calculer(capital: Decimal, taux: Decimal, nb_echeances: int,
             periodicite: str, premiere: date,
             assurance: Decimal = Decimal("0")) -> list[LigneTableau]:
    i = taux_periodique(taux, periodicite)
    dates = dates_echeances(premiere, periodicite, nb_echeances)
    return amortir(capital, i, dates, [assurance] * nb_echeances, 1)


class TableauInvalide(ValueError):
    """Invariant rompu ; `rang` : l'échéance en cause (None : le tableau
    entier), pour que l'import puisse citer la ligne du fichier."""

    def __init__(self, message: str, rang: int | None = None):
        super().__init__(message)
        self.rang = rang


def reliquat_admis(lignes: list[LigneTableau]) -> bool:
    """Un tableau de la BANQUE peut ne pas solder le prêt (décision du
    25/09/2026) : cas constaté sur un tableau actualisé réel, dont la
    dernière ligne laisse un reliquat dû. La banque fait foi ; le capital
    n'étant pas comptabilisé, le reliquat n'a aucun effet sur les comptes :
    il est admis et SIGNALÉ. Un tableau calculé ou corrigé à la main, lui,
    doit solder au centime."""
    return bool(lignes) and lignes[-1].origine == "import"


def reliquat(lignes: list[LigneTableau]) -> Decimal:
    """Capital restant dû après la dernière échéance (0 s'il solde)."""
    return lignes[-1].crd if lignes else Decimal("0")


def verifier_tableau(lignes: list[LigneTableau], crd_depart: Decimal) -> None:
    """Invariants d'un tableau. Lève TableauInvalide en nommant l'échéance."""
    if not lignes:
        raise TableauInvalide("Tableau vide.")
    precedent_rang, precedente_date, crd = None, None, crd_depart
    for x in lignes:
        n = f"Échéance n° {x.rang} ({x.date.strftime('%d/%m/%Y')})"
        if precedent_rang is not None and x.rang != precedent_rang + 1:
            raise TableauInvalide(f"{n} : rang non consécutif.", x.rang)
        if precedente_date is not None and x.date <= precedente_date:
            raise TableauInvalide(f"{n} : date antérieure ou égale à celle de "
                             "l'échéance précédente.", x.rang)
        if x.capital < 0:
            raise TableauInvalide(
                f"{n} : capital amorti négatif ({euros_fr(x.capital)} €). Un "
                "capital restant dû qui augmente (report, capitalisation "
                "d'intérêts) n'est pas pris en charge.", x.rang)
        if x.interets < 0:
            raise TableauInvalide(f"{n} : intérêts négatifs "
                             f"({euros_fr(x.interets)} €).", x.rang)
        if x.assurance < 0:
            raise TableauInvalide(f"{n} : assurance négative "
                             f"({euros_fr(x.assurance)} €).", x.rang)
        if x.origine == "calcul" and x.capital == 0:
            raise TableauInvalide(f"{n} : une échéance calculée doit amortir du "
                             "capital (capital restant dû strictement "
                             "décroissant).", x.rang)
        if x.crd != crd - x.capital:
            raise TableauInvalide(
                f"{n} : capital restant dû {euros_fr(x.crd)} € ≠ "
                f"{euros_fr(crd)} − {euros_fr(x.capital)} €.", x.rang)
        if x.crd < 0:
            raise TableauInvalide(f"{n} : capital restant dû négatif — le capital "
                             "amorti dépasse ce qui reste dû.", x.rang)
        precedent_rang, precedente_date, crd = x.rang, x.date, x.crd
    somme = sum((x.capital for x in lignes), Decimal("0"))
    if somme + crd != crd_depart:                    # garde : chaîne rompue
        raise TableauInvalide("Capitaux amortis et capital restant dû ne "
                              "s'additionnent pas au capital à rembourser.")
    if crd != 0 and not reliquat_admis(lignes):
        raise TableauInvalide(
            f"Le tableau ne solde pas le prêt : la somme des capitaux amortis "
            f"({euros_fr(somme)} €) diffère du capital à rembourser "
            f"({euros_fr(crd_depart)} €) ; {euros_fr(crd)} € restent dus "
            "après la dernière échéance.")


def ecarts_interets(lignes: list[LigneTableau], crd_depart: Decimal,
                    i: Decimal) -> dict[int, Decimal]:
    """Rang → intérêts attendus (CRD × i) quand la ligne en diffère.
    Affiché, jamais bloquant : la banque fait foi (première échéance
    brisée, jours exacts, arrondis propres à l'établissement)."""
    out, crd = {}, crd_depart
    for x in lignes:
        with localcontext() as ctx:
            ctx.prec = 34
            attendu = arrondi(crd * i)
        if attendu != x.interets:
            out[x.rang] = attendu
        crd = x.crd
    return out


# ── Schéma ───────────────────────────────────────────────────────────────

def assurer_schema(conn: sqlite3.Connection) -> None:
    """Tables des emprunts (palier 11). Idempotent, sans commit."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS emprunt ("
        " id                     INTEGER PRIMARY KEY,"
        " bien_id                INTEGER NOT NULL REFERENCES bien(id),"
        " preteur                TEXT    NOT NULL,"
        " reference              TEXT,"
        " capital_c              INTEGER NOT NULL CHECK (capital_c > 0),"
        " taux_nominal           TEXT    NOT NULL,"
        " nb_echeances           INTEGER NOT NULL"
        "                        CHECK (nb_echeances BETWEEN 1 AND 480),"
        " periodicite            TEXT    NOT NULL CHECK (periodicite IN"
        "                        ('mensuelle','trimestrielle','annuelle')),"
        " date_deblocage         TEXT    NOT NULL,"
        " date_premiere_echeance TEXT    NOT NULL,"
        " assurance_c            INTEGER NOT NULL DEFAULT 0"
        "                        CHECK (assurance_c >= 0),"
        " rang_depart            INTEGER NOT NULL DEFAULT 1,"
        " crd_depart_c           INTEGER NOT NULL CHECK (crd_depart_c > 0),"
        " cree_le                TEXT    NOT NULL,"
        " CHECK (date_premiere_echeance >= date_deblocage))")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS emprunt_ligne ("
        " emprunt_id    INTEGER NOT NULL REFERENCES emprunt(id),"
        " rang          INTEGER NOT NULL CHECK (rang >= 1),"
        " date_echeance TEXT    NOT NULL,"
        " capital_c     INTEGER NOT NULL CHECK (capital_c >= 0),"
        " interets_c    INTEGER NOT NULL CHECK (interets_c >= 0),"
        " assurance_c   INTEGER NOT NULL CHECK (assurance_c >= 0),"
        " crd_c         INTEGER NOT NULL CHECK (crd_c >= 0),"
        " origine       TEXT    NOT NULL"
        "               CHECK (origine IN ('calcul','saisie','import')),"
        " PRIMARY KEY (emprunt_id, rang))")
    echeancier.assurer_rang(conn)


def _tables_presentes(conn) -> bool:
    """Une base pas encore migrée n'a pas les tables : les pages et les
    contrôles la traitent comme un dossier sans emprunt."""
    return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                        "AND name IN ('emprunt','emprunt_ligne')"
                        ).fetchone()[0] == 2


# ── Lecture ──────────────────────────────────────────────────────────────

_COLONNES = ("id", "bien_id", "preteur", "reference", "capital_c",
             "taux_nominal", "nb_echeances", "periodicite", "date_deblocage",
             "date_premiere_echeance", "assurance_c", "rang_depart",
             "crd_depart_c", "cree_le")


def _depuis_ligne(row) -> dict:
    e = dict(zip(_COLONNES, row))
    e["capital"] = en_euros(e["capital_c"])
    e["taux"] = Decimal(e["taux_nominal"])
    e["assurance"] = en_euros(e["assurance_c"])
    e["crd_depart"] = en_euros(e["crd_depart_c"])
    e["premiere"] = date.fromisoformat(e["date_premiere_echeance"])
    e["deblocage"] = date.fromisoformat(e["date_deblocage"])
    e["i"] = taux_periodique(e["taux"], e["periodicite"])
    return e


def emprunt(conn: sqlite3.Connection, emprunt_id: int) -> dict:
    row = conn.execute(f"SELECT {', '.join(_COLONNES)} FROM emprunt WHERE id=?",
                       (emprunt_id,)).fetchone()
    if row is None:
        raise ValueError(f"Emprunt n° {emprunt_id} introuvable.")
    return _depuis_ligne(row)


def tableau(conn: sqlite3.Connection, emprunt_id: int) -> list[LigneTableau]:
    return [LigneTableau(r, date.fromisoformat(d), en_euros(c), en_euros(i),
                         en_euros(a), en_euros(crd), o)
            for r, d, c, i, a, crd, o in conn.execute(
                "SELECT rang, date_echeance, capital_c, interets_c, "
                "assurance_c, crd_c, origine FROM emprunt_ligne "
                "WHERE emprunt_id=? ORDER BY rang", (emprunt_id,))]


def rang_verrouille(conn: sqlite3.Connection, emprunt_id: int) -> int:
    """Dernier rang VERROUILLÉ (0 : aucun). Une échéance passée en écriture
    — ou écartée, c'est-à-dire déclarée passée autrement — fige son rang et
    les précédents ; « Rétablir » une échéance écartée la libère."""
    try:
        v = conn.execute(
            "SELECT MAX(rang) FROM echeance_generee WHERE source=? "
            "AND source_id=?", (SOURCE, emprunt_id)).fetchone()[0]
    except sqlite3.OperationalError:          # moteur absent : rien de figé
        return 0
    return v or 0


def crd_au(e: dict, lignes: list[LigneTableau], jour: date) -> Decimal:
    """Capital restant dû au soir du `jour` selon le tableau."""
    if e["rang_depart"] == 1 and jour < e["deblocage"]:
        return Decimal("0")
    crd = e["crd_depart"]
    for x in lignes:
        if x.date > jour:
            break
        crd = x.crd
    return crd


def lister(conn: sqlite3.Connection, bien_id: int | None = None) -> list[dict]:
    """Emprunts du dossier (biens cédés compris), avec leur CRD à ce jour."""
    if not _tables_presentes(conn):
        return []
    try:
        cessions = dict(conn.execute(
            "SELECT id, date_cession FROM bien WHERE date_cession IS NOT NULL "
            "AND date_cession<>''"))
    except sqlite3.OperationalError:
        cessions = {}
    libelles = dict(conn.execute("SELECT id, libelle FROM bien"))
    auj = echeancier._aujourd_hui()
    out = []
    for row in conn.execute(f"SELECT {', '.join(_COLONNES)} FROM emprunt "
                            "ORDER BY id").fetchall():
        e = _depuis_ligne(row)
        if bien_id is not None and e["bien_id"] != bien_id:
            continue
        lignes = tableau(conn, e["id"])
        e.update(bien_libelle=libelles.get(e["bien_id"], "?"),
                 date_cession=cessions.get(e["bien_id"]),
                 crd_aujourd_hui=crd_au(e, lignes, auj),
                 nb_lignes=len(lignes),
                 derniere=lignes[-1].date if lignes else None,
                 verrou=rang_verrouille(conn, e["id"]),
                 taux_pourcent=taux_fr(e["taux"]))
        out.append(e)
    return out


def _ecritures_par_rang(conn, emprunt_id: int) -> dict[int, dict]:
    try:
        rows = conn.execute(
            "SELECT g.rang, g.etat, MIN(e.ecriture_num), MIN(e.exercice_annee),"
            " MAX(COALESCE(o.annulee,0)) FROM echeance_generee g "
            "LEFT JOIN echeance_operation eo ON eo.echeance_id = g.id "
            "LEFT JOIN operation o ON o.id = eo.operation_id "
            "LEFT JOIN ecriture e ON e.id = o.ecriture_id "
            "WHERE g.source=? AND g.source_id=? AND g.rang IS NOT NULL "
            "GROUP BY g.id", (SOURCE, emprunt_id)).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {r: {"etat": etat, "ecriture": num, "exercice": ex,
                "annulee": bool(ann)} for r, etat, num, ex, ann in rows}


def vue(conn: sqlite3.Connection, emprunt_id: int) -> dict:
    """Tout ce qu'affichent l'onglet Emprunts ET l'onglet Immobilisations :
    une seule lecture, aucune copie."""
    e = emprunt(conn, emprunt_id)
    lignes = tableau(conn, emprunt_id)
    verrou = rang_verrouille(conn, emprunt_id)
    ecarts = ecarts_interets(lignes, e["crd_depart"], e["i"])
    e["taux_pourcent"] = taux_fr(e["taux"])
    e["crd_aujourd_hui"] = crd_au(e, lignes, echeancier._aujourd_hui())
    liees = _ecritures_par_rang(conn, emprunt_id)
    crd_avant = e["crd_depart"]
    rows = []
    for x in lignes:
        rows.append({"rang": x.rang, "date": x.date, "crd_avant": crd_avant,
                     "capital": x.capital, "interets": x.interets,
                     "assurance": x.assurance, "echeance": x.echeance,
                     "total": x.total, "crd": x.crd, "origine": x.origine,
                     "verrouillee": x.rang <= verrou,
                     "lien": liees.get(x.rang),
                     "interets_attendus": ecarts.get(x.rang)})
        crd_avant = x.crd
    totaux = {k: sum((getattr(x, k) for x in lignes), Decimal("0"))
              for k in ("capital", "interets", "assurance")}
    return {"emprunt": e, "lignes": rows, "verrou": verrou, "totaux": totaux,
            "nb_ecarts": len(ecarts), "reliquat": reliquat(lignes)}


# ── Écriture du tableau (atomique) ───────────────────────────────────────

def _inserer_ligne(conn, emprunt_id: int, x: LigneTableau) -> None:
    conn.execute(
        "INSERT INTO emprunt_ligne (emprunt_id, rang, date_echeance, "
        "capital_c, interets_c, assurance_c, crd_c, origine) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (emprunt_id, x.rang, x.date.isoformat(), en_centimes(x.capital),
         en_centimes(x.interets), en_centimes(x.assurance),
         en_centimes(x.crd), x.origine))


def _ecrire_tableau(conn, emprunt_id: int, lignes: list[LigneTableau],
                    crd_depart: Decimal) -> None:
    """Remplace le tableau d'un emprunt, dans la transaction de l'appelant.

    Les rangs verrouillés doivent être repris À L'IDENTIQUE : on ne
    réécrit jamais une échéance passée en écriture. Le tableau est
    vérifié avant écriture PUIS relu en base et revérifié : c'est ce qui
    est enregistré qui doit tenir les invariants.
    """
    verifier_tableau(lignes, crd_depart)
    verrou = rang_verrouille(conn, emprunt_id)
    if verrou:
        anciennes = {x.rang: x for x in tableau(conn, emprunt_id)}
        nouvelles = {x.rang: x for x in lignes}
        for r in range(1, verrou + 1):
            a, n = anciennes.get(r), nouvelles.get(r)
            if a is None:
                continue                         # rang antérieur au tableau
            if n is None or (a.date, a.capital, a.interets, a.assurance,
                             a.crd) != (n.date, n.capital, n.interets,
                                        n.assurance, n.crd):
                raise ValueError(
                    f"L'échéance n° {r} est verrouillée (passée en écriture "
                    f"ou écartée) : elle ne peut pas être modifiée. Seules "
                    f"les échéances après la n° {verrou} sont modifiables.")
    conn.execute("DELETE FROM emprunt_ligne WHERE emprunt_id=?", (emprunt_id,))
    for x in lignes:
        _inserer_ligne(conn, emprunt_id, x)
    conn.execute("UPDATE emprunt SET rang_depart=?, crd_depart_c=? WHERE id=?",
                 (lignes[0].rang, en_centimes(crd_depart), emprunt_id))
    verifier_tableau(tableau(conn, emprunt_id), crd_depart)


def _transaction(conn, geste):
    """Tout ou rien. Dans la transaction d'un appelant, un SAVEPOINT (il
    ne committe rien : c'est l'appelant qui valide) ; sinon une transaction
    propre, prise en écriture AVANT de relire le tableau."""
    if conn.in_transaction:
        conn.execute("SAVEPOINT emprunt")
        try:
            r = geste()
        except Exception:
            conn.execute("ROLLBACK TO SAVEPOINT emprunt")
            conn.execute("RELEASE SAVEPOINT emprunt")
            raise
        conn.execute("RELEASE SAVEPOINT emprunt")
        return r
    conn.execute("BEGIN IMMEDIATE")
    try:
        r = geste()
        conn.commit()
        return r
    except Exception:
        conn.rollback()
        raise


# ── Création, modification, suppression ──────────────────────────────────

def _parametres(conn, *, bien_id, preteur, capital, taux, nb_echeances,
                periodicite, date_deblocage, date_premiere_echeance,
                assurance=None, reference=None) -> dict:
    try:
        bien_id = int(bien_id)
    except (TypeError, ValueError):
        raise ValueError("Bien financé : choisissez un bien.") from None
    if not conn.execute("SELECT 1 FROM bien WHERE id=?", (bien_id,)).fetchone():
        raise ValueError(f"Bien n° {bien_id} inconnu.")
    capital = lire_montant(capital, "Capital emprunté")
    if capital <= 0:
        raise ValueError("Le capital emprunté doit être strictement positif.")
    taux = lire_taux(taux)
    if taux < 0:
        raise ValueError("Le taux nominal ne peut pas être négatif.")
    if taux > TAUX_MAX:
        raise ValueError(
            f"Un taux nominal de {taux_fr(taux)} % est invraisemblable "
            f"pour un prêt immobilier (borne : {taux_fr(TAUX_MAX)} %). "
            "Vérifiez la virgule (3,5 et non 35) et que vous n'avez pas "
            "saisi le TAEG.")
    try:
        n = Decimal(str(nb_echeances).strip())
    except InvalidOperation:
        raise ValueError(f"Durée « {nb_echeances} » illisible.") from None
    if n != n.to_integral_value() or n < 1 or n > DUREE_MAX:
        raise ValueError(f"La durée est un nombre ENTIER d'échéances, de 1 à "
                         f"{DUREE_MAX} (reçu : {nb_echeances}).")
    if periodicite not in PERIODICITES:
        raise ValueError(f"Périodicité inconnue : {periodicite!r} "
                         f"({', '.join(PERIODICITES)}).")
    deblocage = lire_date(date_deblocage, "Date de déblocage")
    premiere = lire_date(date_premiere_echeance, "Date de la première échéance")
    if premiere < deblocage:
        raise ValueError("La première échéance ne peut pas précéder le "
                         "déblocage des fonds.")
    assurance = lire_montant(assurance or "0", "Assurance par échéance")
    if assurance < 0:
        raise ValueError("L'assurance par échéance ne peut pas être négative.")
    return {"bien_id": bien_id,
            "preteur": _texte(preteur, "Prêteur", requis=True),
            "reference": _texte(reference, "Référence du prêt"),
            "capital": arrondi(capital), "taux": taux, "nb": int(n),
            "periodicite": periodicite, "deblocage": deblocage,
            "premiere": premiere, "assurance": arrondi(assurance)}


def creer(conn: sqlite3.Connection, **champs) -> int:
    """Décrit un emprunt et calcule son tableau. Tout ou rien."""
    assurer_schema(conn)
    p = _parametres(conn, **champs)
    lignes = calculer(p["capital"], p["taux"], p["nb"], p["periodicite"],
                      p["premiere"], p["assurance"])

    def geste():
        eid = conn.execute(
            "INSERT INTO emprunt (bien_id, preteur, reference, capital_c, "
            "taux_nominal, nb_echeances, periodicite, date_deblocage, "
            "date_premiere_echeance, assurance_c, rang_depart, crd_depart_c, "
            "cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (p["bien_id"], p["preteur"], p["reference"],
             en_centimes(p["capital"]), str(p["taux"]), p["nb"],
             p["periodicite"], p["deblocage"].isoformat(),
             p["premiere"].isoformat(), en_centimes(p["assurance"]),
             en_centimes(p["capital"]),
             datetime.now().isoformat(timespec="seconds"))).lastrowid
        _ecrire_tableau(conn, eid, lignes, p["capital"])
        return eid
    return _transaction(conn, geste)


def modifier(conn: sqlite3.Connection, emprunt_id: int, **champs) -> None:
    """Change les paramètres et RECALCULE le tableau. Refusé dès qu'une
    échéance est verrouillée, ou si le tableau porte des lignes de la
    banque (elles seraient effacées) ; le prêteur et la référence restent
    modifiables par `renommer`."""
    e = emprunt(conn, emprunt_id)
    if rang_verrouille(conn, emprunt_id):
        raise ValueError("Des échéances de cet emprunt sont déjà passées en "
                         "écriture : ses paramètres ne changent plus. "
                         "Corrigez les lignes suivantes du tableau.")
    if any(x.origine != "calcul" for x in tableau(conn, emprunt_id)):
        raise ValueError("Le tableau contient des lignes saisies ou importées "
                         "de la banque : un recalcul les effacerait. "
                         "Réimportez le tableau de la banque à la place.")
    base = {"bien_id": e["bien_id"], "preteur": e["preteur"],
            "reference": e["reference"], "capital": e["capital"],
            "taux": e["taux"], "nb_echeances": e["nb_echeances"],
            "periodicite": e["periodicite"],
            "date_deblocage": e["date_deblocage"],
            "date_premiere_echeance": e["date_premiere_echeance"],
            "assurance": e["assurance"]}
    base.update({k: v for k, v in champs.items() if v is not None})
    p = _parametres(conn, **base)
    lignes = calculer(p["capital"], p["taux"], p["nb"], p["periodicite"],
                      p["premiere"], p["assurance"])

    def geste():
        conn.execute(
            "UPDATE emprunt SET bien_id=?, preteur=?, reference=?, capital_c=?,"
            " taux_nominal=?, nb_echeances=?, periodicite=?, date_deblocage=?,"
            " date_premiere_echeance=?, assurance_c=? WHERE id=?",
            (p["bien_id"], p["preteur"], p["reference"],
             en_centimes(p["capital"]), str(p["taux"]), p["nb"],
             p["periodicite"], p["deblocage"].isoformat(),
             p["premiere"].isoformat(), en_centimes(p["assurance"]),
             emprunt_id))
        _ecrire_tableau(conn, emprunt_id, lignes, p["capital"])
    _transaction(conn, geste)


def renommer(conn: sqlite3.Connection, emprunt_id: int, *, preteur,
             reference=None) -> None:
    emprunt(conn, emprunt_id)
    conn.execute("UPDATE emprunt SET preteur=?, reference=? WHERE id=?",
                 (_texte(preteur, "Prêteur", requis=True),
                  _texte(reference, "Référence du prêt"), emprunt_id))
    conn.commit()


def supprimer(conn: sqlite3.Connection, emprunt_id: int) -> None:
    """Refusé dès qu'une échéance est générée ou écartée : ses écritures
    renverraient à un tableau disparu."""
    emprunt(conn, emprunt_id)
    if rang_verrouille(conn, emprunt_id):
        raise ValueError("Des échéances de cet emprunt sont passées en "
                         "écriture (ou écartées) : il ne peut plus être "
                         "supprimé.")

    def geste():
        conn.execute("DELETE FROM emprunt_ligne WHERE emprunt_id=?",
                     (emprunt_id,))
        conn.execute("DELETE FROM emprunt WHERE id=?", (emprunt_id,))
    _transaction(conn, geste)


# ── Tableau de la banque : remplacement ligne à ligne ────────────────────

def remplacer_ligne(conn: sqlite3.Connection, emprunt_id: int, rang: int, *,
                    date_echeance, capital, interets, assurance="0") -> dict:
    """Remplace l'échéance `rang` par celle de la banque.

    Le CRD de la ligne se déduit (CRD précédent − capital). Si toutes les
    échéances suivantes sont CALCULÉES, elles sont recalculées : le CRD
    restant est amorti à échéances constantes sur le même nombre
    d'échéances, aux mêmes dates — c'est ce que fait la banque après un
    différé (vérifié sur une offre réelle). Des lignes suivantes déjà
    saisies ou importées ne sont jamais recalculées : si elles ne
    s'enchaînent plus, le remplacement est refusé.
    """
    e = emprunt(conn, emprunt_id)
    lignes = tableau(conn, emprunt_id)
    rang = int(rang)
    pos = next((k for k, x in enumerate(lignes) if x.rang == rang), None)
    if pos is None:
        raise ValueError(f"L'échéance n° {rang} n'existe pas dans ce tableau.")
    verrou = rang_verrouille(conn, emprunt_id)
    if rang <= verrou:
        raise ValueError(f"L'échéance n° {rang} est verrouillée (passée en "
                         "écriture ou écartée) : elle ne peut pas être "
                         "modifiée.")
    crd_avant = lignes[pos - 1].crd if pos else e["crd_depart"]
    nouvelle = LigneTableau(
        rang, lire_date(date_echeance, "Date de l'échéance"),
        lire_montant(capital, "Capital amorti"),
        lire_montant(interets, "Intérêts"),
        lire_montant(assurance or "0", "Assurance"), Decimal("0"), "saisie")
    nouvelle.crd = crd_avant - nouvelle.capital
    suite = lignes[pos + 1:]
    recalcul = bool(suite) and all(x.origine == "calcul" for x in suite)
    if recalcul and nouvelle.crd > 0:
        suite = amortir(nouvelle.crd, e["i"], [x.date for x in suite],
                        [x.assurance for x in suite], rang + 1)
    resultat = lignes[:pos] + [nouvelle] + suite
    _transaction(conn, lambda: _ecrire_tableau(conn, emprunt_id, resultat,
                                               e["crd_depart"]))
    return {"recalculees": len(suite) if recalcul else 0,
            "ecart_interets": ecarts_interets(
                [nouvelle], crd_avant, e["i"]).get(rang)}


# ── Tableau de la banque : import CSV ────────────────────────────────────

COLONNES_CSV = ("date", "échéance", "capital", "intérêts", "assurance",
                "capital restant dû")


def _decoder(contenu) -> str:
    if isinstance(contenu, str):
        return contenu
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenu.decode("cp1252")


def _separateur(texte: str) -> str:
    premiere = next((x for x in texte.splitlines() if x.strip()), "")
    for sep in (";", "\t"):
        if sep in premiere:
            return sep
    return ","


def lire_csv(contenu) -> tuple[list[dict], dict]:
    """Lit le tableau de la banque. TOUT OU RIEN : la première ligne en
    erreur fait rejeter le fichier, avec son numéro.

    Colonnes (dans cet ordre) : date ; échéance ; capital ; intérêts ;
    assurance ; capital restant dû. Ligne d'en-tête facultative.

    Deux présentations bancaires sont admises, reconnues sur le fichier
    entier puis imposées à toutes les lignes :
      - l'échéance avec ou sans l'assurance ;
      - le capital restant dû AVANT l'échéance (« en début de période »,
        la présentation des deux tableaux réels examinés) ou APRÈS.
    """
    texte = _decoder(contenu)
    sep = _separateur(texte)
    lignes, decimales = [], set()
    for num, row in enumerate(csv.reader(io.StringIO(texte), delimiter=sep),
                              start=1):
        cellules = [c.strip() for c in row]
        while cellules and not cellules[-1]:
            cellules.pop()
        if not cellules:
            continue
        if not lignes and not re.match(r"^\d", cellules[0]):
            continue                                  # en-tête
        if len(cellules) != 6:
            raise ValueError(f"Ligne {num} : {len(cellules)} colonne(s), 6 "
                             f"attendues ({' ; '.join(COLONNES_CSV)}).")
        try:
            jour = lire_date(cellules[0], "date")
            valeurs = {}
            for nom, cell in zip(("echeance", "capital", "interets",
                                  "assurance", "crd"), cellules[1:]):
                if nom == "assurance" and not cell:
                    cell = "0"
                valeurs[nom] = lire_montant(cell, nom)
                if "," in cell:
                    decimales.add(",")
                elif "." in cell:
                    decimales.add(".")
        except ValueError as exc:
            raise ValueError(f"Ligne {num} : {exc}") from None
        if len(decimales) > 1:
            raise ValueError(f"Ligne {num} : séparateur décimal différent de "
                             "celui des lignes précédentes — fichier refusé "
                             "plutôt que deviné.")
        lignes.append({"num": num, "date": jour, **valeurs})
    if not lignes:
        raise ValueError("Fichier vide : aucune échéance lue.")

    # Présentation de l'échéance : avec ou sans assurance.
    avec = next((x["echeance"] == x["capital"] + x["interets"] + x["assurance"]
                 for x in lignes if x["assurance"] != 0), False)
    for x in lignes:
        attendu = x["capital"] + x["interets"] + (x["assurance"] if avec
                                                  else 0)
        if x["echeance"] != attendu:
            raise ValueError(
                f"Ligne {x['num']} : échéance {euros_fr(x['echeance'])} ≠ "
                f"capital + intérêts{' + assurance' if avec else ''} "
                f"({euros_fr(attendu)}).")

    # Présentation du CRD : avant ou après l'échéance.
    def rupture(avant: bool) -> int | None:
        for k in range(1, len(lignes)):
            p, x = lignes[k - 1], lignes[k]
            attendu = (p["crd"] - p["capital"]) if avant \
                else (p["crd"] - x["capital"])
            if x["crd"] != attendu:
                return k
        return None
    r_avant, r_apres = rupture(True), rupture(False)
    if r_avant is None and r_apres is None:
        # Capitaux tous égaux : le solde final tranche.
        avant = lignes[-1]["crd"] == lignes[-1]["capital"] != 0
    elif r_avant is None or r_apres is None:
        avant = r_avant is None
    else:
        k = max(r_avant, r_apres)
        x = lignes[k]
        raise ValueError(f"Ligne {x['num']} : le capital restant dû "
                         f"({euros_fr(x['crd'])}) ne s'enchaîne pas avec la "
                         "ligne précédente.")
    crd_depart = lignes[0]["crd"] if avant \
        else lignes[0]["crd"] + lignes[0]["capital"]
    for x in lignes:
        if avant:
            x["crd"] = x["crd"] - x["capital"]
    return lignes, {"crd_depart": crd_depart, "assurance_comprise": avec,
                    "crd_avant_echeance": avant}


def importer_csv(conn: sqlite3.Connection, emprunt_id: int, contenu) -> dict:
    """Remplace le tableau par celui de la banque, à partir de l'échéance
    dont le fichier donne la première date. Tout ou rien : un fichier
    refusé laisse le tableau intact."""
    e = emprunt(conn, emprunt_id)
    try:
        lus, info = lire_csv(contenu)
    except ValueError as exc:
        raise ValueError(f"Fichier refusé, tableau inchangé. {exc}") from None
    actuel = tableau(conn, emprunt_id)
    par_date = {x.date: x for x in actuel}
    debut = lus[0]["date"]
    if debut in par_date:
        k = par_date[debut].rang
    elif not actuel or debut == e["premiere"]:
        k = 1
    else:
        raise ValueError(
            f"Fichier refusé, tableau inchangé. Sa première date "
            f"({debut.strftime('%d/%m/%Y')}) n'est celle d'aucune échéance "
            "du tableau : le fichier doit commencer à la première échéance, "
            "ou à celle à partir de laquelle vous reprenez le prêt.")
    verrou = rang_verrouille(conn, emprunt_id)
    if verrou and k > verrou + 1:
        raise ValueError(
            f"Fichier refusé, tableau inchangé. Il commence à l'échéance "
            f"n° {k}, mais les échéances jusqu'à la n° {verrou} sont "
            f"verrouillées : il doit reprendre au plus tard à la n° "
            f"{verrou + 1}.")
    lignes = [LigneTableau(k + j, x["date"], x["capital"], x["interets"],
                           x["assurance"], x["crd"], "import")
              for j, x in enumerate(lus)]
    crd_depart = info["crd_depart"]
    if verrou and k > 1:
        # Les rangs verrouillés antérieurs au fichier restent tels quels,
        # et le fichier doit s'y raccorder.
        garde = [x for x in actuel if x.rang < k]
        if garde and garde[-1].crd != crd_depart:
            raise ValueError(
                f"Fichier refusé, tableau inchangé. Il part d'un capital "
                f"restant dû de {euros_fr(crd_depart)} €, mais l'échéance "
                f"n° {k - 1}, verrouillée, laisse {euros_fr(garde[-1].crd)} €.")
        lignes = garde + lignes
        crd_depart = e["crd_depart"]
    num = {k + j: x["num"] for j, x in enumerate(lus)}
    try:
        _transaction(conn, lambda: _ecrire_tableau(conn, emprunt_id, lignes,
                                                   crd_depart))
    except TableauInvalide as exc:
        ou = f"Ligne {num[exc.rang]} : " if exc.rang in num else ""
        raise ValueError(f"Fichier refusé, tableau inchangé. {ou}{exc}") \
            from None
    except ValueError as exc:
        raise ValueError(f"Fichier refusé, tableau inchangé. {exc}") from None
    return {"nb": len(lus), "premier_rang": k,
            "ecarts_interets": len(ecarts_interets(lignes, crd_depart,
                                                   e["i"])),
            "reliquat": reliquat(lignes), **info}


def exporter_csv(conn: sqlite3.Connection, emprunt_id: int) -> str:
    """Tableau au format relu par `importer_csv` (point-virgule, virgule
    décimale, CRD après l'échéance, échéance hors assurance)."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(["Date", "Échéance (hors assurance)", "Capital", "Intérêts",
                "Assurance", "Capital restant dû après échéance"])
    for x in tableau(conn, emprunt_id):
        w.writerow([x.date.strftime("%d/%m/%Y")]
                   + [f"{v:.2f}".replace(".", ",")
                      for v in (x.echeance, x.capital, x.interets,
                                x.assurance, x.crd)])
    return out.getvalue()


# ── Source du moteur d'échéances ─────────────────────────────────────────

def _saisis_hors_tableau(conn) -> list[tuple[date, Decimal]]:
    """Intérêts ou assurances d'emprunt saisis HORS de la génération (à la
    main, en fin d'année, ou rangés dans une autre charge avec un libellé
    qui les nomme) : (date, montant) de chaque opération non annulée."""
    return [(date.fromisoformat(d), Decimal(str(m))) for d, m in conn.execute(
        "SELECT date_operation, montant FROM operation "
        "WHERE COALESCE(annulee,0)=0 AND source<>? AND ("
        " type IN ('interets_emprunt','assurance_emprunteur')"
        " OR LOWER(COALESCE(libelle,'')) LIKE '%intérêt%'"
        " OR LOWER(COALESCE(libelle,'')) LIKE '%interet%')", (SOURCE,))]


def echeances(conn: sqlite3.Connection, du: date, au: date,
              emprunt_ids: set[int] | None = None) -> list[echeancier.Echeance]:
    """Une échéance du moteur par ligne du tableau datée dans [du, au]."""
    if not _tables_presentes(conn):
        return []
    hors_tableau = _saisis_hors_tableau(conn)
    out = []
    for e in lister(conn):
        if emprunt_ids is not None and e["id"] not in emprunt_ids:
            continue
        lignes = tableau(conn, e["id"])
        dernier = lignes[-1].rang if lignes else 0
        # Seules comptent les saisies faites PENDANT la période couverte par
        # le tableau : pendant les déblocages successifs, les intérêts se
        # saisissent à la main, et le tableau n'est décrit (ou importé)
        # qu'à partir de l'échéance où le prêt suit son cours normal.
        debut = lignes[0].date if lignes else None
        deja: dict[int, tuple[int, Decimal]] = {}
        for d, m in hors_tableau:
            if debut is not None and d >= debut:
                n, t = deja.get(d.year, (0, Decimal("0")))
                deja[d.year] = (n + 1, t + m)
        for x in lignes:
            if not du <= x.date <= au:
                continue
            periode = f"{x.date.year:04d}-{x.date.month:02d}"
            piece = f"ECH {e['id']}-{x.rang}"
            ops = []
            if x.interets > 0:
                ops.append({"type": "interets_emprunt",
                            "montant": float(x.interets), "periode": periode,
                            "libelle": f"Intérêts échéance {x.rang}/{dernier}"
                                       f" - {e['preteur']}",
                            "piece_ref": piece})
            if x.assurance > 0:
                ops.append({"type": "assurance_emprunteur",
                            "montant": float(x.assurance), "periode": periode,
                            "libelle": f"Assurance emprunteur échéance "
                                       f"{x.rang}/{dernier} - {e['preteur']}",
                            "piece_ref": piece})
            alertes = []
            if x.date.year in deja:
                n, total = deja[x.date.year]
                alertes.append(
                    f"L'exercice {x.date.year} porte déjà {n} opération(s) "
                    f"d'intérêts ou d'assurance d'emprunt saisie(s) hors de "
                    f"ce tableau ({euros_fr(total)} €) : générer les "
                    "échéances les compterait deux fois. Annulez-les "
                    "d'abord, ou écartez ces échéances.")
            out.append(echeancier.Echeance(
                source=SOURCE, source_id=e["id"], date=x.date,
                bien_id=e["bien_id"],
                libelle=f"Échéance {x.rang}/{dernier} - {e['preteur']}",
                operations=ops, alertes=alertes, decochee=bool(alertes),
                motif_source=None if ops else
                "ni intérêts ni assurance : aucune charge à comptabiliser",
                ecriture_unique=True, rang=x.rang,
                montant_total=float(x.total)))
    return out


def apercu(conn, du: date, au: date, *, emprunt_ids=None,
           aujourd_hui: date | None = None):
    return echeancier.apercu(conn, echeances(conn, du, au, emprunt_ids),
                             aujourd_hui=aujourd_hui)


def generer(conn, du: date, au: date, retenues: set[str], *,
            ecarter: set[str] = frozenset(), emprunt_ids=None,
            aujourd_hui: date | None = None) -> dict:
    return echeancier.generer(conn, echeances(conn, du, au, emprunt_ids),
                              retenues, ecarter=ecarter,
                              aujourd_hui=aujourd_hui)


def alerte_reliquat(montant: Decimal) -> str:
    return (f"Le tableau de la banque ne solde pas le prêt : "
            f"{euros_fr(montant)} € restent dus après sa dernière échéance. "
            "Accepté — la banque fait foi, et le capital n'est pas "
            "comptabilisé — mais demandez-lui la ligne de solde : elle "
            "portera des intérêts à passer en écriture.")


def message_generation(r: dict) -> str:
    n = len(r["creees"])
    msg = (f"{n} échéance(s) passée(s) en écriture ({r['nb_operations']} "
           "opération(s))")
    if r["ecartees"]:
        msg += f", {len(r['ecartees'])} échéance(s) écartée(s)"
    msg += "."
    if r["non_generees"]:
        msg += (f" {len(r['non_generees'])} échéance(s) retenue(s) n'étaient "
                "plus à générer : elles n'ont pas été créées.")
    return msg


# ── Contrôles (appelés par controles.py) ─────────────────────────────────

def _exercice(conn, annee: int) -> tuple[date, date] | None:
    row = conn.execute("SELECT date_debut, date_fin FROM exercice "
                       "WHERE annee=?", (annee,)).fetchone()
    return (date.fromisoformat(row[0]), date.fromisoformat(row[1])) \
        if row else None


def _solde(conn, annee: int, compte: str, *, an_seulement: bool = False,
           credit: bool = False, depuis: date | None = None) -> Decimal:
    sql = ("SELECT ROUND(COALESCE(SUM(l.debit - l.credit),0),2) FROM ligne l "
           "JOIN ecriture e ON e.id = l.ecriture_id WHERE e.exercice_annee=? "
           "AND l.compte_num=?")
    params: list = [annee, compte]
    if an_seulement:
        sql += " AND e.journal_code='AN'"
    if depuis is not None:
        sql += " AND e.ecriture_date>=?"
        params.append(depuis.isoformat())
    s = Decimal(str(conn.execute(sql, params).fetchone()[0]))
    return -s if credit else s


def ecart_interets(conn, annee: int) -> dict | None:
    """Intérêts des échéances ÉCHUES de l'exercice selon les tableaux,
    contre le solde 661100 de l'exercice. None sans emprunt décrit."""
    if not _tables_presentes(conn):
        return None
    emprunts = lister(conn)
    bornes = _exercice(conn, annee)
    if not emprunts or bornes is None:
        return None
    fin = min(bornes[1], echeancier._aujourd_hui())
    # Période comparée : du début de l'exercice, ou du premier tableau s'il
    # commence en cours d'année (déblocages successifs saisis à la main
    # avant lui : ils n'ont pas de tableau à qui se comparer).
    debuts = [x[0].date for x in (tableau(conn, e["id"]) for e in emprunts)
              if x]
    depuis = max(bornes[0], min(debuts)) if debuts else bornes[0]
    prevus = Decimal("0")
    for e in emprunts:
        cession = (date.fromisoformat(e["date_cession"])
                   if e["date_cession"] else None)
        prevus += sum((x.interets for x in tableau(conn, e["id"])
                       if depuis <= x.date <= fin
                       and (cession is None or x.date <= cession)),
                      Decimal("0"))
    comptes = _solde(conn, annee, "661100", depuis=depuis)
    return {"prevus": prevus, "comptabilises": comptes,
            "ecart": comptes - prevus, "du": depuis, "au": fin}


def ecart_crd(conn, annee: int) -> dict | None:
    """CRD des tableaux au dernier jour de l'exercice (et à l'ouverture)
    contre le compte 164000. None si le dossier ne porte pas ce compte :
    le capital n'étant pas comptabilisé, il n'y a rien à rapprocher."""
    if not _tables_presentes(conn):
        return None
    emprunts = lister(conn)
    bornes = _exercice(conn, annee)
    if not emprunts or bornes is None:
        return None
    if not conn.execute(
            "SELECT 1 FROM ligne l JOIN ecriture e ON e.id = l.ecriture_id "
            "WHERE l.compte_num='164000' AND e.exercice_annee<=? LIMIT 1",
            (annee,)).fetchone():
        return None
    veille = bornes[0] - timedelta(days=1)
    theo_fin = theo_ouv = Decimal("0")
    for e in emprunts:
        lignes = tableau(conn, e["id"])
        theo_fin += crd_au(e, lignes, bornes[1])
        theo_ouv += crd_au(e, lignes, veille)
    return {"theorique_fin": theo_fin,
            "compte_fin": _solde(conn, annee, "164000", credit=True),
            "theorique_ouverture": theo_ouv,
            "compte_ouverture": _solde(conn, annee, "164000",
                                       an_seulement=True, credit=True),
            "fin": bornes[1], "ouverture": bornes[0]}


def materiel(ecart: Decimal) -> bool:
    return abs(ecart) >= SEUIL_ECART
