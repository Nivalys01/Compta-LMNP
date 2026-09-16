# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Plan des immobilisations : LA source unique.

Pourquoi ce fichier existe
--------------------------
Le couple « compte d'immobilisation → compte d'amortissement » était exprimé
dans dix fichiers, dont deux le portaient en dur et en double :

  - `app.py` — COMPTES_IMMO, pour le menu de la page Immobilisations, donc
    dans la COUCHE WEB : une connaissance comptable logée dans la
    présentation ;
  - `liasse.py` — RUBRIQUES_2033C, pour les rubriques et les cases du 2033-C.

Aucun des deux ne référençait l'autre. Ajouter un compte — un agencement sur
un 2181 distinct, un véhicule — demandait d'y penser à dix endroits, et le
risque n'était pas d'en oublier un : c'était qu'un oubli reste invisible,
chaque module continuant de fonctionner avec sa propre vue partielle.

Ce module ne contient QUE ce qui se déduisait autrement. Les colonnes
`composant.compte_immo` / `compte_amort` du schéma, les comptes du
référentiel et les jeux de test gardent leur place : ce sont des données, pas
une correspondance.

Cases relevées sur le CERFA 2033-C-SD 2026 (n° 15948*08) : cadre I pour le
brut, cadre II pour les amortissements.
"""
from __future__ import annotations

# L'ORDRE est celui du formulaire : terrains, constructions, installations,
# autres. Les dictionnaires Python le conservent, ce qui évite une seconde
# liste à tenir en accord.
IMMOBILISATIONS: dict[str, dict] = {
    "211550": {
        "libelle": "Terrain",                     # menu de saisie
        "amort": None,                            # un terrain ne s'amortit pas
        "rubrique": "terrains",
        "rubrique_libelle": "Terrains",           # libellé CERFA
        "case_brut": "420", "case_amort": "510",
    },
    "213150": {
        "libelle": "Bâtiment",
        "amort": "281315",
        "rubrique": "constructions",
        "rubrique_libelle": "Constructions",
        "case_brut": "430", "case_amort": "520",
    },
    "218100": {
        "libelle": "Installation / agencement",
        "amort": "281810",
        "rubrique": "installations",
        "rubrique_libelle": "Installations générales, agencements",
        "case_brut": "450", "case_amort": "540",
    },
    "218400": {
        "libelle": "Mobilier",
        "amort": "281840",
        "rubrique": "autres_immo",
        "rubrique_libelle": "Autres immobilisations corporelles",
        "case_brut": "470", "case_amort": "560",
    },
}


def pour_la_saisie() -> list[tuple[str, str, str | None]]:
    """(compte, libellé, compte d'amortissement) — menu de la page
    Immobilisations. Remplace le COMPTES_IMMO qui vivait dans `app.py`."""
    return [(n, f["libelle"], f["amort"]) for n, f in IMMOBILISATIONS.items()]


def pour_le_2033c() -> dict[str, tuple[str, str, str, str]]:
    """{compte: (clé de rubrique, libellé CERFA, case brut, case amort.)} —
    remplace le RUBRIQUES_2033C qui vivait dans `liasse.py`."""
    return {n: (f["rubrique"], f["rubrique_libelle"],
                f["case_brut"], f["case_amort"])
            for n, f in IMMOBILISATIONS.items()}


def ordre_rubriques() -> list[str]:
    """Clés de rubrique, dans l'ordre du formulaire."""
    return [f["rubrique"] for f in IMMOBILISATIONS.values()]


def resoudre(compte_immo: str) -> str | None:
    """Le compte du plan dont `compte_immo` est une SUBDIVISION, ou None.

    Les comptes du plan livré tiennent sur six chiffres. Un cabinet en
    utilise couramment sept — 2181000 pour ce que ce plan nomme 218100 — et
    la reprise d'un FEC les crée tels quels. Toute correspondance était
    établie par égalité STRICTE : 2181000 n'était donc rattaché à rien, et
    ses montants tombaient dans le repli « autres immobilisations » du
    2033-C, dans la mauvaise rubrique du formulaire, sans que le total
    général ne bouge d'un centime — donc sans qu'aucun contrôle de
    concordance puisse le voir.

    On reconnaît désormais la subdivision par son PRÉFIXE, le plus long
    d'abord. Ce qui ne correspond à aucun compte du plan reste non résolu :
    2180000, compte générique, ne dit pas de quelle nature physique relève
    le composant, et cela s'annonce (voir `c_compte_immo_inconnu`) plutôt
    que de se deviner.
    """
    compte_immo = (compte_immo or "").strip()
    if not compte_immo:
        return None
    if compte_immo in IMMOBILISATIONS:
        return compte_immo
    for connu in sorted(IMMOBILISATIONS, key=len, reverse=True):
        if compte_immo.startswith(connu):
            return connu
    return None


def fiche(compte_immo: str) -> dict | None:
    """La fiche du plan correspondant au compte, subdivisions comprises."""
    resolu = resoudre(compte_immo)
    return IMMOBILISATIONS[resolu] if resolu else None


def compte_amortissement(compte_immo: str) -> str | None:
    """Compte d'amortissement d'une immobilisation, None si non amortissable."""
    return (fiche(compte_immo) or {}).get("amort")


def amortissement_coherent(compte_immo: str, compte_amort: str) -> bool:
    """Le compte d'amortissement va-t-il avec le compte d'immobilisation ?

    Les subdivisions sont admises DES DEUX CÔTÉS : un cabinet qui tient son
    agencement en 2181000 l'amortit en 2818100, et les deux sont bien les
    subdivisions à sept chiffres de 218100 et 281810. Comparer les chaînes
    à l'identique rejetterait ce couple parfaitement correct ; ne rien
    comparer du tout laisse passer un terrain amorti sur un compte de
    mobilier.
    """
    if resoudre(compte_immo) is None:
        # Compte étranger au plan livré — le compte générique 2180000 d'un
        # cabinet, par exemple. On ne sait pas ce qu'il devrait amortir :
        # c'est INJUGEABLE, pas incohérent. Refuser ici bloquerait la
        # clôture de tout dossier repris d'un FEC externe ; l'alerte
        # `COMPTE_IMMO_INCONNU` dit ce qu'il y a à dire.
        return True
    attendu = compte_amortissement(compte_immo)
    compte_amort = (compte_amort or "").strip()
    if attendu is None:
        return not compte_amort          # non amortissable : aucun compte 28
    return bool(compte_amort) and compte_amort.startswith(attendu)
