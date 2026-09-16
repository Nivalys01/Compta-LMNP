# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Génère à la demande le paquet client distribuable, depuis la racine du dépôt :

    python build_client.py            → dist/compta_lmnp_client_vX.Y.Z.zip

Le dépôt ne versionne PAS de dossier `compta_lmnp_client` : le paquet est un
artefact, il se reconstruit. Le travail réel est fait par
`construire_distribution.py`, livré dans `compta_lmnp/`, qui
embarque les gardes anti-fuite (ni base .db, ni `reference/`, ni
`seed_exemple.sql`, ni `tests/` dans le zip — la construction échoue plutôt
que de laisser passer une donnée personnelle). Ce script se contente de
localiser l'arborescence courante et de l'appeler, pour qu'il n'existe qu'un
seul point d'entrée à connaître.
"""
from __future__ import annotations

import os
import runpy

RACINE = os.path.dirname(os.path.abspath(__file__))

# Le dossier du logiciel ne porte plus de numéro de version. Il en portait un
# — `compta_lmnp_v8.41.0/` — et ce script devait donc trier des candidats sur
# les nombres du nom, parce que 8.9.0 passe après 8.41.0 en tri lexical. Un
# chemin qui change à chaque version est intenable dans un dépôt public : il
# casse les clones, les liens permanents et les signets. La version vit
# désormais dans le fichier VERSION, et nulle part ailleurs.
SOURCE = os.path.join(RACINE, "compta_lmnp")


def trouver_source() -> str:
    """Renvoie le dossier `compta_lmnp/`, et vérifie qu'il est bien là."""
    if not os.path.isfile(os.path.join(SOURCE, "construire_distribution.py")):
        raise SystemExit(
            f"Arborescence introuvable : {SOURCE} ne contient pas "
            "construire_distribution.py — rien à empaqueter.")
    return SOURCE


def main() -> None:
    source = trouver_source()
    print(f"→ Construction depuis {os.path.relpath(source, RACINE)}")
    # Exécuté dans son propre dossier : le script résout ses chemins et son
    # numéro de version relativement à lui-même.
    # Le script appelé termine lui-même le processus (code 0 s'il a produit
    # le paquet, 1 avec un message si une garde a bloqué la construction).
    runpy.run_path(os.path.join(source, "construire_distribution.py"),
                   run_name="__main__")


if __name__ == "__main__":
    main()
