# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Génère à la demande le paquet client distribuable, depuis la racine du dépôt :

    python build_client.py            → dist/compta_lmnp_client_vX.Y.Z.zip

Le dépôt ne versionne PAS de dossier `compta_lmnp_client` : le paquet est un
artefact, il se reconstruit. Le travail réel est fait par
`construire_distribution.py`, livré dans l'arborescence versionnée, qui
embarque les gardes anti-fuite (ni base .db, ni `reference/`, ni
`seed_exemple.sql`, ni `tests/` dans le zip — la construction échoue plutôt
que de laisser passer une donnée personnelle). Ce script se contente de
localiser l'arborescence courante et de l'appeler, pour qu'il n'existe qu'un
seul point d'entrée à connaître.
"""
from __future__ import annotations

import glob
import os
import runpy

RACINE = os.path.dirname(os.path.abspath(__file__))


def trouver_source() -> str:
    """Renvoie le dossier `compta_lmnp/` de la version la plus récente."""
    candidats = sorted(
        os.path.dirname(chemin)
        for chemin in glob.glob(
            os.path.join(RACINE, "compta_lmnp_v*", "compta_lmnp",
                         "construire_distribution.py")))
    if not candidats:
        raise SystemExit(
            "Aucune arborescence compta_lmnp_v*/compta_lmnp/ trouvée sous "
            f"{RACINE} : rien à empaqueter.")
    # Les versions se trient correctement en numérique, pas en texte
    # (8.9.0 > 8.41.0 en tri lexical) : on classe sur les nombres du nom.
    def cle(dossier: str) -> list[int]:
        nom = os.path.basename(os.path.dirname(dossier))
        return [int(n) for n in nom.split("_v")[-1].split(".") if n.isdigit()]
    return max(candidats, key=cle)


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
