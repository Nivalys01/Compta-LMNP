# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

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


def compte_amortissement(compte_immo: str) -> str | None:
    """Compte d'amortissement d'une immobilisation, None si non amortissable."""
    return (IMMOBILISATIONS.get(compte_immo) or {}).get("amort")
