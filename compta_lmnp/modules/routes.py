# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Point d'enregistrement UNIQUE des modules de routes (`modules/*_web.py`).

Chaque groupe de routes cohérent — un onglet, une fonction — vit dans son
module `<nom>_web.py`, qui expose `enregistrer_routes(app, ctx)`. Le
routeur principal ne les nomme pas : il appelle `enregistrer_tous`, qui les
trouve en LISANT LE RÉPERTOIRE. Ajouter une fonction, c'est ajouter son
module ; `app.py` ne gagne pas une ligne.

Pourquoi pas une liste : une énumération écrite à la main ne peut pas
signaler ce qu'on a oublié d'y mettre (règle 5 des invariants d'audit —
vue deux fois dans ce projet). Un module présent mais oublié dans la liste
laissait ses routes répondre 404 sans que rien ne le dise. La même raison
fait embarquer tout `modules/` par `construire_distribution.py`.

Et pas de silence non plus : un module `*_web.py` qui ne s'importe pas, ou
qui n'expose pas `enregistrer_routes`, fait ÉCHOUER le démarrage en le
nommant — plutôt qu'un onglet absent découvert par l'utilisateur.

Les routes sont enregistrées sur l'application elle-même, pas dans un
blueprint : leurs noms (`url_for("immobilisations")`) restent ceux de leur
fonction, et les gardes globales (`gardes_http`) les couvrent toutes.
"""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Callable

DOSSIER = os.path.dirname(os.path.abspath(__file__))
SUFFIXE = "_web.py"


@dataclass(frozen=True)
class ContexteWeb:
    """Les fonctions du routeur dont les modules de routes ont besoin.

    Elles restent dans `app.py` parce qu'elles portent l'état du routeur
    (dossier actif, bac à sable, connexion fermée en fin de requête, mise
    en page commune) ; les modules les reçoivent ici, sous une signature
    unique.
    """
    conn: Callable
    annee_param: Callable
    annees: Callable
    base: Callable
    db_path: Callable
    dossier_imports: Callable


def modules_web(dossier: str = DOSSIER) -> list[str]:
    """Noms des modules de routes présents, dans un ordre stable."""
    return sorted(f[:-3] for f in os.listdir(dossier)
                  if f.endswith(SUFFIXE) and not f.startswith("."))


def enregistrer_tous(app, ctx: ContexteWeb, dossier: str = DOSSIER) -> list[str]:
    """Enregistre les routes de chaque module `*_web.py`. Renvoie leurs noms."""
    noms = modules_web(dossier)
    for nom in noms:
        try:
            module = importlib.import_module(nom)
        except Exception as exc:
            raise RuntimeError(
                f"Le module de routes « {nom}.py » ne se charge pas "
                f"({type(exc).__name__} : {exc}). Ses pages seraient "
                "absentes : le logiciel refuse de démarrer sans elles.") from exc
        enregistrer = getattr(module, "enregistrer_routes", None)
        if not callable(enregistrer):
            raise RuntimeError(
                f"Le module « {nom}.py » porte le suffixe des modules de "
                "routes mais n'expose pas enregistrer_routes(app, ctx). "
                "Renommez-le, ou ajoutez cette fonction.")
        enregistrer(app, ctx)
    return noms
