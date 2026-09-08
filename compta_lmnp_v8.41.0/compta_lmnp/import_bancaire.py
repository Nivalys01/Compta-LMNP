# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Import de relevé bancaire (CSV) avec pré-catégorisation par mots-clés.

Le relevé bancaire EST la source des mouvements réels : l'importer supprime
l'essentiel de la frappe. Chaque ligne est rapprochée d'un type d'opération ;
ce qui n'est pas reconnu tombe en 'autres_charges' (donc signalé à requalifier
par les contrôles — comportement prudent, pas silencieux).

Format CSV attendu (séparateur ;, tabulation ou ,) :
    date(JJ/MM/AAAA ou AAAA-MM-JJ);libelle;montant
EXACTEMENT trois colonnes. Montant signé : positif = encaissement, négatif
= décaissement ; les formes -120,50 / 120,50- / (120,50) / -120,50 EUR /
-1 234,50 € sont toutes acceptées.

Un export à colonnes débit et crédit séparées est REFUSÉ, pas deviné : il
était lu comme un montant positif et transformait toutes les charges en
recettes. Toute ligne dont le montant reste illisible est comptée et
restituée par analyser() — jamais ignorée en silence.
"""
from __future__ import annotations
import csv
import io
import re
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


# Séparateurs de milliers (espace ordinaire, insécable, fine insécable) et
# marques de devise que les exports bancaires accolent au montant.
_PARASITES_MONTANT = (" ", "\xa0", " ", "€")


def _montant(brut: str) -> float:
    """Convertit un montant d'export bancaire en flottant SIGNÉ.

    Les banques françaises écrivent le même débit d'au moins cinq façons :
    -120,50 ; 120,50- (signe suffixe, hérité des mainframes) ; (120,50)
    (convention comptable anglo-saxonne) ; -120,50 EUR ; -1 234,50 €.
    Seule la première était lue ; les autres disparaissaient de l'import
    sans un mot, et l'utilisateur concluait que son relevé était vide.

    Lève ValueError si la chaîne reste illisible — à charge de l'appelant
    de COMPTER le rejet et de le restituer, jamais de l'avaler.
    """
    s = (brut or "").strip()
    for p in _PARASITES_MONTANT:
        s = s.replace(p, "")
    s = re.sub(r"(?i)eur", "", s).strip()   # « EUR » ne peut pas être un chiffre
    negatif = False
    if s.startswith("(") and s.endswith(")"):      # (120,50) = -120,50
        negatif, s = True, s[1:-1].strip()
    if s.endswith("-"):                            # 120,50-  = -120,50
        negatif, s = True, s[:-1].strip()
    if not s:
        raise ValueError("montant vide")
    valeur = float(s.replace(",", "."))
    return -abs(valeur) if negatif else valeur


def _delimiteur(texte: str) -> str:
    """Devine le séparateur de colonnes sur le début du fichier.

    Le point-virgule l'emporte à égalité : dans un export français la
    virgule est d'abord un séparateur DÉCIMAL (120,50), donc fréquente
    sans être le délimiteur. La tabulation est reconnue depuis la passe E
    — un export tabulé était auparavant lu comme une colonne unique, donc
    intégralement rejeté (constat E-03).
    """
    debut = texte[:2048]
    comptes = {c: debut.count(c) for c in (";", "\t", ",")}
    meilleur = max(comptes.values())
    if meilleur == 0:
        return ";"
    for c in (";", "\t", ","):             # ordre = priorité à égalité
        if comptes[c] == meilleur:
            return c
    return ";"


def analyser(csv_path: str, conn=None) -> dict:
    """Lit le relevé et rend compte de TOUT : ce qui est proposé, et ce qui
    ne l'est pas.

    Renvoie {"propositions": [...], "rejets": [...]}, chaque rejet portant
    son numéro de ligne, son contenu et la raison. Un import partiel qui se
    présente comme complet est le pire des résultats : le déclarant ne peut
    pas savoir que des charges manquent à l'appel.

    Robustesse (les exports bancaires réels sont sales) :
    - encodage : UTF-8 (avec ou sans BOM) puis repli cp1252 — les banques
      françaises exportent souvent en encodage Windows ;
    - un fichier binaire (PDF renommé…) est refusé avec un message clair ;
    - séparateur : point-virgule, tabulation ou virgule ;
    - montants : voir _montant() ;
    - libellés : tabulations et sauts de ligne remplacés par des espaces
      (interdits au guichet — un relevé bancaire peut en contenir).

    Refuse le FICHIER (et non la ligne) dès qu'une ligne de données ne porte
    pas exactement trois colonnes : un export « Date;Libellé;Débit;Crédit »
    se lisait auparavant sans erreur, la colonne débit étant prise pour un
    montant signé — toutes les charges devenaient des recettes (E-02).
    """
    with open(csv_path, "rb") as f:
        brut = f.read()
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

    delim = _delimiteur(texte)
    propositions: list[dict] = []
    rejets: list[dict] = []
    for n, r in enumerate(csv.reader(io.StringIO(texte), delimiter=delim), 1):
        if not r or all(not c.strip() for c in r):
            continue                          # ligne vide
        if _norm(r[0]) in ("date", "date operation"):
            continue                          # en-tête
        if len(r) != 3:
            raise ValueError(
                f"Ligne {n} : {len(r)} colonnes au lieu de 3. Ce module lit "
                "un relevé « date;libelle;montant », le montant étant signé "
                "(négatif pour un décaissement). Il ne sait pas lire un "
                "export à colonnes débit et crédit séparées : il prendrait "
                "chaque débit pour une recette, et toutes vos charges "
                "deviendraient des loyers. Réexportez le relevé en trois "
                "colonnes, ou supprimez les colonnes en trop avant l'import.")
        try:
            montant = _montant(r[2])
        except ValueError:
            rejets.append({"ligne": n, "contenu": delim.join(r).strip(),
                           "raison": f"montant illisible ({r[2].strip()!r})"})
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
    return {"propositions": propositions, "rejets": rejets}


def proposer(csv_path: str, conn=None) -> list[dict]:
    """Propositions d'opérations (non insérées) issues du relevé.

    Ne dit RIEN des lignes rejetées : passer par analyser() partout où
    l'utilisateur doit les voir.
    """
    return analyser(csv_path, conn)["propositions"]


def importer(conn, csv_path: str, valider: bool = False) -> list[dict]:
    """Propose (et insère si valider=True) les opérations issues du relevé."""
    props = proposer(csv_path, conn)
    if valider:
        for p in props:
            operations.saisir(conn, source="import_bancaire", **p)
    return props
