# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Import de relevé bancaire (CSV) avec pré-catégorisation par mots-clés.

Le relevé bancaire EST la source des mouvements réels : l'importer supprime
l'essentiel de la frappe. Chaque ligne est rapprochée d'un type d'opération ;
ce qui n'est pas reconnu tombe en 'autres_charges' (donc signalé à requalifier
par les contrôles — comportement prudent, pas silencieux).

Format CSV attendu (séparateur ; ou ,) : date(JJ/MM/AAAA ou AAAA-MM-JJ);libelle;montant
Montant signé : positif = encaissement, négatif = décaissement.
"""
from __future__ import annotations
import csv
import io
import operations

# Mots-clés -> type de gabarit. Ordre = priorité (premier match gagne).
REGLES = [
    (("loyer", "rent"),                         "loyer"),
    (("pno", "assurance", "gmf", "maif", "matmut", "emprunteur"), "assurance"),
    (("syndic", "copro", "copropriete"),        "charge_copro"),
    (("orange", "free", "sfr", "bouygues", "internet", "box", "fibre"), "telecom"),
    (("chaudiere", "entretien", "reparation", "plomb", "depannage"), "maintenance"),
    (("taxe fonciere", "teom", "tresor public", "dgfip", "impot local"), "impot_local"),
    (("cfe", "cotisation fonciere"),            "cfe"),
    (("les acteurs payants actuels", "comptab", "expert comptable"),   "honoraires"),
    (("frais", "commission", "cotisation carte", "agios"), "frais_bancaires"),
    (("ikea", "electromenager", "darty", "boulanger", "mobilier"), "petit_equipement"),
]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _date_iso(s: str) -> str:
    s = s.strip()
    if "/" in s:                       # JJ/MM/AAAA
        j, m, a = s.split("/")
        return f"{a}-{int(m):02d}-{int(j):02d}"
    return s                            # déjà AAAA-MM-JJ


def categoriser(libelle: str, montant: float, conn=None) -> str:
    """Renvoie le type de gabarit proposé pour une ligne de relevé.
    Priorité 1 : l'HISTORIQUE des saisies validées (un libellé déjà rencontré
    reprend son type — vos propres saisies sont le meilleur référentiel).
    Priorité 2 : les mots-clés génériques. Sinon : autres_charges (signalé)."""
    if conn is not None:
        t = suggerer_depuis_historique(conn, libelle)
        if t:
            return t
    if montant > 0:
        return "loyer"                 # encaissement : loyer par défaut
    lib = _norm(libelle)
    for cles, type_op in REGLES:
        if any(k in lib for k in cles):
            return type_op
    return "autres_charges"            # décaissement non reconnu -> à requalifier


def suggerer_depuis_historique(conn, libelle: str) -> str | None:
    """Type le plus fréquemment associé à ce libellé (normalisé) dans les
    opérations déjà saisies, tous exercices confondus. None si inconnu ou
    si l'historique ne pointe que vers un fourre-tout."""
    lib = _norm(libelle)
    if len(lib) < 4:
        return None
    row = conn.execute(
        "SELECT type, COUNT(*) AS n FROM operation "
        "WHERE LOWER(TRIM(COALESCE(libelle,''))) = ? AND source='saisie' "
        "GROUP BY type ORDER BY n DESC LIMIT 1", (lib,)).fetchone()
    if row and row[0] != "autres_charges":
        return row[0]
    return None


def proposer(csv_path: str, conn=None) -> list[dict]:
    """Lit le relevé et renvoie des propositions d'opérations (non insérées).

    Robustesse (les exports bancaires réels sont sales) :
    - encodage : UTF-8 (avec ou sans BOM) puis repli cp1252 — les banques
      françaises exportent souvent en encodage Windows ;
    - un fichier binaire (PDF renommé…) est refusé avec un message clair ;
    - montants : tous les séparateurs de milliers Unicode sont nettoyés
      (espace, insécable \xa0, fine insécable \u202f) — sinon la ligne
      serait ignorée EN SILENCE, une perte de données invisible ;
    - libellés : tabulations et sauts de ligne remplacés par des espaces
      (interdits au guichet — un relevé bancaire peut en contenir).
    """
    brut = open(csv_path, "rb").read()
    texte = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texte is None or "\x00" in texte:
        raise ValueError("Ce fichier n'est pas un relevé CSV lisible "
                         "(fichier binaire ? mauvais fichier ?). Exportez le "
                         "relevé au format CSV depuis votre banque.")

    delim = ";" if texte[:2048].count(";") >= texte[:2048].count(",") else ","
    propositions = []
    for r in csv.reader(io.StringIO(texte), delimiter=delim):
        if len(r) < 3:
            continue
        if _norm(r[0]) in ("date", "date operation"):
            continue               # en-tête
        montant_brut = r[2].strip()
        for sep in (" ", "\xa0", "\u202f"):
            montant_brut = montant_brut.replace(sep, "")
        try:
            montant = float(montant_brut.replace(",", "."))
        except ValueError:
            continue
        date = _date_iso(r[0])
        libelle = " ".join(r[1].split())       # tabs/newlines → espace simple
        type_op = categoriser(libelle, montant, conn)
        mensuel = type_op in ("loyer", "charges_locatives")
        propositions.append({
            "date_operation": date,
            "libelle": libelle,
            "montant": round(abs(montant), 2),
            "type": type_op,
            "periode": date[:7] if mensuel else None,
        })
    return propositions


def importer(conn, csv_path: str, valider: bool = False) -> list[dict]:
    """Propose (et insère si valider=True) les opérations issues du relevé."""
    props = proposer(csv_path, conn)
    if valider:
        for p in props:
            operations.saisir(conn, source="import_bancaire", **p)
    return props
