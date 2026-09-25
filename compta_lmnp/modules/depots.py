# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Suivi des dépôts — « cette déclaration est partie, tel jour, sous telle
référence ».

Fonction purement DÉCLARATIVE : elle ne crée aucune écriture, ne touche ni
au FEC, ni à la liasse, ni à aucun calcul, et ne parle à aucun service
extérieur. Elle consigne un fait survenu HORS du logiciel.

Deux suivis par exercice, parce qu'il y a deux dépôts dans deux espaces
distincts d'impots.gouv.fr : la liasse 2031/2033 (espace professionnel) et
la 2042-C-PRO (espace particulier). Pour chacun, une seule déclaration
initiale, puis autant de rectificatives que nécessaire.

À l'enregistrement, les chiffres que le logiciel calcule À CET INSTANT sont
mémorisés (instantané). Ils sont lus dans `liasse` et dans le résultat de
clôture posé par `fiscal.cloturer` — jamais recalculés ici : une seconde
formule finirait par diverger de la première. Si l'exercice est ensuite
rouvert (restauration d'une sauvegarde d'avant clôture) puis reclôturé avec
d'autres chiffres, l'écart est signalé à CHAQUE lecture — même principe que
la confrontation des quittances aux écritures.

Les contrôles de ce module restent HORS de `controles.CONTROLES` : la
liasse embarque les anomalies du moteur, et enregistrer un dépôt ne doit
pas modifier la liasse.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from controles import AVERTISSEMENT, INFO, Anomalie

TYPES = {
    "liasse_2031": "Liasse 2031 / 2033 (espace professionnel)",
    "2042_c_pro": "2042-C-PRO (espace particulier)",
}
# Noms courts acceptés par la ligne de commande.
ALIAS = {"liasse": "liasse_2031", "2031": "liasse_2031",
         "2042": "2042_c_pro", "2042c": "2042_c_pro"}
NATURES = ("initiale", "rectificative")

# Un numéro d'accusé de réception de la DGFiP tient largement en 64
# caractères ; au-delà, c'est un copier-coller qui a débordé.
LONGUEUR_REFERENCE = 64
LONGUEUR_NOTE = 200

LIBELLES = {
    "resultat_fiscal": "Résultat fiscal LMNP (2033-B)",
    "resultat_fiscal_cloture": "Résultat fiscal de clôture",
    "5NA": "Case 5NA (bénéfice)", "5NY": "Case 5NY (déficit)",
}
for _l in "ABCDEFGHIJ":
    LIBELLES[f"5G{_l}"] = f"Case 5G{_l} (déficit antérieur)"

_INDISPONIBLE = "_indisponible"


def _aujourd_hui() -> date:
    """Horloge du module — remplacée dans les tests (web et CLI compris)."""
    return date.today()


def assurer_schema(conn: sqlite3.Connection) -> None:
    """Crée la table si besoin (palier de migration 9). Idempotent.

    Pas de `commit` : de la DDL hors transaction est validée d'elle-même,
    et un `commit` ici validerait en silence la transaction d'un appelant.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS depot_declaration ("
        " id             INTEGER PRIMARY KEY,"
        " exercice_annee INTEGER NOT NULL REFERENCES exercice(annee),"
        " type           TEXT NOT NULL"
        "                CHECK (type IN ('liasse_2031','2042_c_pro')),"
        " nature         TEXT NOT NULL"
        "                CHECK (nature IN ('initiale','rectificative')),"
        " date_depot     TEXT NOT NULL,"
        " reference      TEXT,"
        " note           TEXT,"
        " chiffres_json  TEXT NOT NULL,"
        " enregistre_le  TEXT NOT NULL)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_depot_initiale "
        "ON depot_declaration(exercice_annee, type) WHERE nature = 'initiale'")


def type_normalise(valeur: str) -> str:
    t = (valeur or "").strip().lower()
    t = ALIAS.get(t, t)
    if t not in TYPES:
        raise ValueError(f"Type de déclaration inconnu : « {valeur} ». "
                         "Attendu : liasse (2031/2033) ou 2042 (2042-C-PRO).")
    return t


# ── Instantané des chiffres déclarés ─────────────────────────────────────

def chiffres_actuels(conn: sqlite3.Connection, annee: int, type_: str) -> dict:
    """Chiffres que le logiciel produit maintenant pour cette déclaration.

    Lus, jamais recalculés : `liasse.resultat_2033b` et `liasse.aide_2042c`
    pour les montants reportés, `exercice.resultat_fiscal` pour celui que
    `fiscal.cloturer` a figé.
    """
    import liasse
    if type_ == "liasse_2031":
        b = liasse.resultat_2033b(conn, annee)
        rf = conn.execute("SELECT resultat_fiscal FROM exercice WHERE annee=?",
                          (annee,)).fetchone()
        return {"resultat_fiscal": round(b["resultat_fiscal_lmnp"], 2),
                "resultat_fiscal_cloture":
                    None if rf is None or rf[0] is None else round(rf[0], 2)}
    aide = liasse.aide_2042c(conn, annee)
    out = {"5NA": aide["case_5NA"], "5NY": aide["case_5NY"]}
    for c in aide["cases_deficits_anterieurs"]:
        out[c["case"]] = c["montant"]
    return out


def _instantane(conn, annee, type_) -> dict:
    # Un instantané impossible ne doit pas empêcher de consigner un dépôt
    # réellement effectué : on l'enregistre, et l'impossibilité est DITE à
    # chaque lecture plutôt que prise pour « rien n'a changé ».
    try:
        return chiffres_actuels(conn, annee, type_)
    except Exception as exc:                         # noqa: BLE001
        return {_INDISPONIBLE: f"{type(exc).__name__} : {exc}"}


# ── Saisie ───────────────────────────────────────────────────────────────

def _texte(valeur: str | None, quoi: str, longueur: int) -> str | None:
    if valeur is None:
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in valeur):
        raise ValueError(f"{quoi} : tabulation, saut de ligne et caractères "
                         "de contrôle sont refusés — une seule ligne de "
                         "texte.")
    valeur = valeur.strip()
    if len(valeur) > longueur:
        raise ValueError(f"{quoi} trop longue : {len(valeur)} caractères, "
                         f"{longueur} au plus.")
    return valeur or None


def _date(valeur: str) -> date:
    try:
        if len(valeur) != 10:
            raise ValueError
        return date.fromisoformat(valeur)
    except (TypeError, ValueError):
        raise ValueError(f"Date de dépôt invalide : « {valeur} » "
                         "(format attendu AAAA-MM-JJ).") from None


def _initiale(conn, annee, type_) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, date_depot FROM depot_declaration WHERE exercice_annee=? "
        "AND type=? AND nature='initiale'", (annee, type_)).fetchone()


def enregistrer(conn: sqlite3.Connection, *, annee: int, type: str,
                nature: str, date_depot: str, reference: str | None = None,
                note: str | None = None,
                aujourd_hui: date | None = None) -> int:
    """Consigne un dépôt. Renvoie son identifiant.

    Tout refus lève `ValueError` AVANT la moindre écriture.
    """
    assurer_schema(conn)
    type_ = type_normalise(type)
    if nature not in NATURES:
        raise ValueError(f"Nature inconnue : « {nature} » "
                         "(initiale ou rectificative).")
    ex = conn.execute("SELECT statut, date_fin FROM exercice WHERE annee=?",
                      (annee,)).fetchone()
    if ex is None:
        raise ValueError(f"L'exercice {annee} n'existe pas dans ce dossier.")
    if ex[0] != "clos":
        raise ValueError(f"L'exercice {annee} n'est pas clôturé : ses "
                         "chiffres sont provisoires, il n'y a pas encore de "
                         "déclaration définitive à déposer.")
    d = _date(date_depot)
    auj = aujourd_hui or _aujourd_hui()
    if d > auj:
        raise ValueError(f"Date de dépôt dans le futur ({d.isoformat()}) : "
                         "on n'enregistre qu'un dépôt déjà effectué.")
    if d <= date.fromisoformat(ex[1]):
        raise ValueError(f"Date de dépôt ({d.isoformat()}) antérieure ou égale "
                         f"à la fin de l'exercice ({ex[1]}) : une déclaration "
                         "se dépose après la clôture de l'exercice.")
    reference = _texte(reference, "Référence de l'accusé", LONGUEUR_REFERENCE)
    note = _texte(note, "Note", LONGUEUR_NOTE)

    # Lecture des chiffres AVANT d'ouvrir la transaction : les fonctions de
    # la liasse n'ont pas à s'exécuter sous notre verrou d'écriture.
    chiffres = _instantane(conn, annee, type_)

    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        ini = _initiale(conn, annee, type_)
        if nature == "initiale" and ini is not None:
            raise ValueError(
                f"Une déclaration initiale est déjà enregistrée pour "
                f"{TYPES[type_]} {annee} (déposée le {ini[1]}). Un nouveau "
                "dépôt est une rectificative.")
        if nature == "rectificative":
            if ini is None:
                raise ValueError(
                    f"Rectificative refusée : aucune déclaration initiale "
                    f"n'est enregistrée pour {TYPES[type_]} {annee}. "
                    "Enregistrez d'abord l'initiale.")
            if d.isoformat() < ini[1]:
                raise ValueError(
                    f"Rectificative datée du {d.isoformat()}, avant "
                    f"l'initiale du {ini[1]} : une rectificative suit "
                    "toujours la déclaration qu'elle corrige.")
        cur = conn.execute(
            "INSERT INTO depot_declaration (exercice_annee, type, nature, "
            "date_depot, reference, note, chiffres_json, enregistre_le) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (annee, type_, nature, d.isoformat(), reference, note,
             json.dumps(chiffres, ensure_ascii=False, sort_keys=True),
             datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise


def supprimer(conn: sqlite3.Connection, depot_id: int) -> dict:
    """Efface un dépôt (ligne entière). Renvoie la ligne supprimée."""
    assurer_schema(conn)
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT id, exercice_annee, type, nature, date_depot "
            "FROM depot_declaration WHERE id=?", (depot_id,)).fetchone()
        if row is None:
            raise ValueError(f"Aucun dépôt n° {depot_id} dans ce dossier.")
        _, annee, type_, nature, date_depot = row
        if nature == "initiale":
            n = conn.execute(
                "SELECT COUNT(*) FROM depot_declaration WHERE exercice_annee=? "
                "AND type=? AND nature='rectificative'",
                (annee, type_)).fetchone()[0]
            if n:
                raise ValueError(
                    f"Cette déclaration initiale a {n} rectificative(s) "
                    "enregistrée(s) : supprimez-les d'abord, sinon elles "
                    "resteraient sans la déclaration qu'elles corrigent.")
        conn.execute("DELETE FROM depot_declaration WHERE id=?", (depot_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"id": depot_id, "annee": annee, "type": type_, "nature": nature,
            "date_depot": date_depot}


# ── Lecture ──────────────────────────────────────────────────────────────

def lister(conn: sqlite3.Connection, annee: int) -> dict[str, list[dict]]:
    """Dépôts de l'exercice, par type, dans l'ordre chronologique."""
    assurer_schema(conn)
    out: dict[str, list[dict]] = {t: [] for t in TYPES}
    for r in conn.execute(
            "SELECT id, type, nature, date_depot, reference, note, "
            "chiffres_json, enregistre_le FROM depot_declaration "
            "WHERE exercice_annee=? ORDER BY date_depot, id", (annee,)):
        out[r[1]].append({
            "id": r[0], "type": r[1], "nature": r[2], "date_depot": r[3],
            "reference": r[4], "note": r[5],
            "chiffres": json.loads(r[6]), "enregistre_le": r[7]})
    return out


def initiales(conn: sqlite3.Connection, annee: int) -> dict[str, str]:
    """{type: date de l'initiale} pour les déclarations déjà déposées."""
    assurer_schema(conn)
    return dict(conn.execute(
        "SELECT type, date_depot FROM depot_declaration "
        "WHERE exercice_annee=? AND nature='initiale'", (annee,)).fetchall())


def _egal(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) < 0.005


def _fmt(v) -> str:
    if v is None:
        return "vide"
    return f"{float(v):,.2f} €".replace(",", " ").replace(".", ",")


def ecarts(declares: dict, actuels: dict) -> list[dict]:
    """Cases dont la valeur actuelle diffère de la valeur déclarée."""
    out = []
    for cle in sorted(set(declares) | set(actuels)):
        avant, apres = declares.get(cle), actuels.get(cle)
        if not _egal(avant, apres):
            out.append({"cle": cle, "libelle": LIBELLES.get(cle, cle),
                        "declare": avant, "actuel": apres,
                        "ecart": None if avant is None or apres is None
                        else round(float(apres) - float(avant), 2)})
    return out


def controler(conn: sqlite3.Connection, annee: int) -> list[Anomalie]:
    """Anomalies propres au suivi des dépôts (hors moteur de contrôles)."""
    assurer_schema(conn)
    ex = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                      (annee,)).fetchone()
    if ex is None:
        return []
    depots = lister(conn, annee)
    out: list[Anomalie] = []
    if ex[0] != "clos":
        for type_, liste in depots.items():
            if liste:
                out.append(Anomalie(
                    INFO, "DEPOT_EXERCICE_ROUVERT",
                    f"{TYPES[type_]} : l'exercice {annee} a été rouvert "
                    f"depuis le dépôt du {liste[-1]['date_depot']}. Ses "
                    "chiffres sont provisoires ; la comparaison avec ce qui "
                    "a été déclaré reprendra à la clôture."))
        return out
    for type_, liste in depots.items():
        if not liste:
            out.append(Anomalie(
                INFO, "DEPOT_ABSENT",
                f"Exercice {annee} clôturé : aucun dépôt enregistré pour "
                f"{TYPES[type_]}. Une fois la déclaration déposée, notez-le "
                "depuis la page Liasse."))
            continue
        dernier = liste[-1]
        declares = dernier["chiffres"]
        if _INDISPONIBLE in declares:
            out.append(Anomalie(
                INFO, "DEPOT_NON_COMPARABLE",
                f"{TYPES[type_]} : les chiffres n'ont pas pu être mémorisés "
                f"lors de l'enregistrement du dépôt du "
                f"{dernier['date_depot']} ({declares[_INDISPONIBLE]}). Un "
                "changement ultérieur ne pourra PAS être détecté."))
            continue
        try:
            actuels = chiffres_actuels(conn, annee, type_)
        except Exception as exc:                     # noqa: BLE001
            out.append(Anomalie(
                AVERTISSEMENT, "DEPOT_COMPARAISON_IMPOSSIBLE",
                f"{TYPES[type_]} : les chiffres actuels ne se lisent plus "
                f"({type(exc).__name__} : {exc}). La concordance avec le "
                f"dépôt du {dernier['date_depot']} n'est donc PAS vérifiée."))
            continue
        diff = ecarts(declares, actuels)
        if diff:
            detail = " ; ".join(
                f"{e['libelle']} : déclaré {_fmt(e['declare'])}, "
                f"aujourd'hui {_fmt(e['actuel'])}"
                + ("" if e["ecart"] is None
                   else f" (écart {'+' if e['ecart'] > 0 else ''}"
                        f"{_fmt(e['ecart'])})")
                for e in diff)
            out.append(Anomalie(
                AVERTISSEMENT, "DEPOT_ECART",
                f"{TYPES[type_]} {annee} : les chiffres ont changé depuis le "
                f"dépôt du {dernier['date_depot']}. {detail}. Une "
                "déclaration rectificative peut être nécessaire."))
    return out


def etat(conn: sqlite3.Connection, annee: int) -> dict:
    """Tout ce que l'affichage a besoin de savoir, en une lecture."""
    ex = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                      (annee,)).fetchone()
    depots = lister(conn, annee)
    return {"annee": annee, "clos": bool(ex) and ex[0] == "clos",
            "types": [{"code": t, "libelle": lib, "depots": depots[t],
                       "a_initiale": any(d["nature"] == "initiale"
                                         for d in depots[t])}
                      for t, lib in TYPES.items()],
            "anomalies": controler(conn, annee),
            "aujourd_hui": _aujourd_hui().isoformat()}


def resume(conn: sqlite3.Connection, annee: int) -> str:
    """Une ligne d'état, pour la page Clôture."""
    ini = initiales(conn, annee)
    return " · ".join(
        f"{'2031/2033' if t == 'liasse_2031' else '2042-C-PRO'} : "
        + (f"déposée le {ini[t]}" if t in ini else "non enregistrée")
        for t in TYPES)


def message_suppression(r: dict) -> str:
    return (f"Dépôt supprimé : {TYPES[r['type']]} {r['annee']}, "
            f"{r['nature']} du {r['date_depot']}.")


# ── Restauration : un dépôt est un fait du monde réel ────────────────────

def lire_pour_report(chemin: str) -> list[tuple] | None:
    """Dépôts d'une base, pour les reporter dans une base restaurée.

    None si la base ne se lit pas (ou n'a pas encore la table) : c'est alors
    la sauvegarde qui fait foi. Une liste — éventuellement vide — si elle se
    lit : c'est elle qui fait foi, y compris pour une suppression.
    """
    try:
        c = sqlite3.connect(chemin)
        try:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                             "AND name='depot_declaration'").fetchone():
                return None
            return c.execute(
                "SELECT id, exercice_annee, type, nature, date_depot, "
                "reference, note, chiffres_json, enregistre_le "
                "FROM depot_declaration ORDER BY id").fetchall()
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return None


def annees_de(chemin: str) -> set[int]:
    c = sqlite3.connect(chemin)
    try:
        return {r[0] for r in c.execute("SELECT annee FROM exercice")}
    finally:
        c.close()


def orphelins(depots: list[tuple], sauvegarde: str) -> list[str]:
    """Dépôts dont l'exercice n'existe pas dans la sauvegarde (décrits)."""
    annees = annees_de(sauvegarde)
    return [f"{TYPES[d[2]]} {d[1]}, {d[3]} du {d[4]}"
            + (f" (accusé {d[5]})" if d[5] else "")
            for d in depots if d[1] not in annees]


def reporter(chemin: str, depots: list[tuple]) -> None:
    """Remplace les dépôts de la base restaurée par ceux de la base d'avant."""
    c = sqlite3.connect(chemin)
    try:
        c.execute("PRAGMA foreign_keys = ON")
        assurer_schema(c)
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM depot_declaration")
        c.executemany(
            "INSERT INTO depot_declaration (id, exercice_annee, type, nature, "
            "date_depot, reference, note, chiffres_json, enregistre_le) "
            "VALUES (?,?,?,?,?,?,?,?,?)", depots)
        c.commit()
    finally:
        c.close()
