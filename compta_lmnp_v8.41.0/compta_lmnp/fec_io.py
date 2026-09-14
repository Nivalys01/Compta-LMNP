# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Lecture des fichiers FEC — socle COMMUN aux trois consommateurs.

Avant cette refonte, trois lecteurs coexistaient (validateur, balance de
reprise, rejeu d'exercice), chacun ré-implémentant l'ouverture du fichier,
le découpage tabulaire et la conversion des montants à virgule. Trois
endroits où un même bug d'encodage ou de séparateur pouvait diverger.

Ce module ne fait QUE l'entrée-sortie :
  - `COLONNES` : les 18 colonnes de l'arrêté A-47 A-1, dans l'ordre —
    source unique (le validateur les réexporte pour compatibilité) ;
  - `lire_brut()` : tokenisation pure, sans filtre ni normalisation — le
    validateur garde ainsi tout son pouvoir de détection (lignes
    incomplètes, en-tête inexact…) ;
  - `lignes_nommees()` : les lignes exploitables, sous forme de dicts
    {colonne: valeur}, pour les consommateurs métier (rejeu) ;
  - `nombre()` : montant FEC (virgule décimale, champ vide = 0).

Les RÈGLES restent chez chaque consommateur : le validateur décide ce qui
est conforme, la reprise décide quelles lignes portent une balance, le
rejeu décide comment insérer. L'écriture (export_fec) reste volontairement
séparée : le validateur doit pouvoir contredire l'export, pas partager ses
défauts.
"""
from __future__ import annotations

import csv

COLONNES = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate",
    "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib",
    "PieceRef", "PieceDate", "EcritureLib", "Debit", "Credit",
    "EcritureLet", "DateLet", "ValidDate", "Montantdevise", "Idevise",
]


def nombre(s: str) -> float:
    """Montant FEC : virgule décimale, blanc = 0. Lève ValueError sur un
    contenu non numérique (chaque consommateur décide quoi en faire)."""
    s = (s or "").strip().replace(",", ".")
    return float(s) if s else 0.0


ENCODAGES = ("utf-8-sig", "cp1252", "iso-8859-15")


def lire_texte(chemin: str) -> str:
    """Contenu du fichier, quel que soit son encodage.

    L'arrêté A47 A-1 autorise explicitement l'ISO-8859-15 en plus de
    l'UTF-8, et c'est ce que produisent plusieurs logiciels de cabinet.
    Le lecteur n'acceptait que l'UTF-8 strict : un FEC parfaitement
    conforme provoquait une `UnicodeDecodeError` brute — y compris dans le
    validateur, dont c'était précisément le rôle de le dire.

    `utf-8-sig` est essayé en premier : il lit l'UTF-8 ordinaire ET retire
    la marque d'ordre des octets qu'ajoutent Excel et plusieurs
    exporteurs. Sans ce retrait, le premier en-tête devenait
    « \ufeffJournalCode » et le rejeu s'arrêtait sur un `KeyError`
    incompréhensible.
    """
    derniere = None
    for enc in ENCODAGES:
        try:
            with open(chemin, encoding=enc, newline="") as f:
                return f.read()
        except UnicodeDecodeError as exc:
            derniere = exc
    raise ValueError(
        "Le fichier n'a pu être lu dans aucun encodage connu "
        "(UTF-8, Windows-1252, ISO-8859-15). Il est peut-être corrompu, "
        "ou ce n'est pas un fichier FEC."
    ) from derniere


def type_du_compte(numero: str) -> str:
    """Type PCG déduit du numéro, pour un compte absent du plan livré.

    Un FEC de cabinet contient presque toujours des comptes que le plan
    livré ne connaît pas (401 fournisseurs, 512 banque, 615 entretien…).
    Il faut donc pouvoir les créer à la volée — et la colonne `type` est
    NOT NULL, contrainte à une liste fermée.

    Les comptes d'amortissement et de dépréciation ont leur type propre :
    ce sont des comptes d'actif SOUSTRACTIF, et les ranger en passif
    fausserait le bilan.
    """
    numero = (numero or "").strip()
    if not numero:
        return "attente"
    if numero.startswith(("28", "29", "39", "49", "59")):
        return "amortissement"
    if numero.startswith("47"):
        return "attente"
    # La classe 4 — les comptes de TIERS — ne se déduit pas de son premier
    # chiffre : 401 fournisseurs est au passif, 411 clients à l'actif. Tout
    # ranger en passif contredisait le plan livré, qui déclare bien `411000`
    # en `actif` : un FEC de cabinet portant des auxiliaires (411DUPONT,
    # 4110000001) créait donc des créances typées comme des dettes.
    #
    # Seules les tranches SANS ambiguïté sont tranchées ici. 44 (État),
    # 45 (associés), 46 (divers) et 48 (régularisation) sont mixtes par
    # construction — c'est le SENS DU SOLDE qui décide, pas le numéro : elles
    # restent au repli, et le bilan LMNP les ignore de toute façon (la
    # comptabilité est tenue sans comptes de tiers, cf. constat E-22).
    if numero.startswith(("40", "42", "43")):
        return "passif"                  # fournisseurs, personnel, organismes
    if numero.startswith("41"):
        return "actif"                   # clients, locataires : une CRÉANCE
    return {"1": "passif", "2": "actif", "3": "actif", "4": "passif",
            "5": "actif", "6": "charge", "7": "produit",
            "8": "attente"}.get(numero[0], "attente")


def assurer_comptes(conn, comptes) -> list[str]:
    """Crée les comptes absents du plan. Renvoie ceux qui ont été créés.

    Sans cela, la reprise d'un FEC externe échouait sur une
    `FOREIGN KEY constraint failed` brute — message qui ne dit rien à
    l'utilisateur et ne nomme même pas le compte en cause.
    """
    crees = []
    for numero, libelle in comptes:
        numero = (numero or "").strip()
        if not numero:
            continue
        if conn.execute("SELECT 1 FROM compte WHERE numero=?",
                        (numero,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO compte (numero, libelle, type, classe) "
            "VALUES (?,?,?,?)",
            (numero, (libelle or numero).strip()[:120],
             type_du_compte(numero), int(numero[0])))
        crees.append(numero)
    return crees


def lire_brut(chemin: str) -> tuple[list[str], list[list[str]]]:
    """(en-tête, lignes) tels quels — tokenisation tabulaire uniquement.
    Aucune ligne n'est filtrée : les lignes vides ou incomplètes sont
    rendues telles quelles pour que le validateur puisse les signaler.

    QUOTE_NONE est essentiel. Le format FEC ne donne AUCUN rôle au
    guillemet : c'est un caractère de texte comme un autre dans un
    libellé. Or le lecteur CSV de Python le traite par défaut comme un
    délimiteur de champ — un seul guillemet non refermé dans un libellé
    faisait donc fusionner toutes les lignes jusqu'au suivant, et elles
    disparaissaient silencieusement de la balance. Sur un vrai FEC, une
    paire déséquilibrée peut escamoter des centaines d'écritures sans que
    rien ne le signale.
    """
    contenu = lire_texte(chemin)
    rows = list(csv.reader(contenu.splitlines(), delimiter="\t",
                           quoting=csv.QUOTE_NONE))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def lignes_nommees(chemin: str) -> list[dict[str, str]]:
    """Lignes exploitables (≥ 18 champs, non vides), en dicts nommés d'après
    l'EN-TÊTE DU FICHIER — un FEC aux colonnes ordonnées différemment reste
    lisible, comme le faisait le rejeu historique."""
    entete, lignes = lire_brut(chemin)
    if not entete:
        return []
    return [dict(zip(entete, r)) for r in lignes
            if len(r) >= len(COLONNES) and any(x.strip() for x in r)]
