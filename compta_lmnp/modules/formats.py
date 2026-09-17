# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Formatage des valeurs affichées — présentation pure.

Ni `app.py`, ni `pages.py` : le point d'entrée est déjà au plafond que lui
impose sa garde anti-monolithe, et `pages.py` doit rester INERTE — des
chaînes de gabarits, sans un import ni une fonction, ce qu'une autre garde
vérifie. Un formateur est du code ; il lui fallait donc son propre module.

Aucune dépendance applicative : ce module ne connaît ni la base, ni le
dossier actif, ni les routes.
"""
from __future__ import annotations

from jinja2 import Undefined

# Branché par app.py au démarrage. Sans lui, les fonctions restent
# utilisables — elles rendent le même texte — mais leurs avertissements ne
# rejoignent pas le journal persistant. Importer l'application pour pouvoir
# écrire dans son journal créerait le cycle que ce module évite.
JOURNAL = None


def _avertir(motif, *args):
    if JOURNAL is not None:
        JOURNAL(motif, *args)


def eur(x) -> str:
    """Montant formaté pour la liasse — et JAMAIS une page en moins.

    Un champ absent du modèle arrive ici en `Undefined` Jinja, pas en
    `None` : le formater faisait tomber l'onglet Liasse tout entier en 500,
    pour un seul champ, sans le nommer. Planter prive le déclarant de tous
    ses autres chiffres ; rendre « — » serait pire encore, un montant
    ABSENT passant alors pour un montant NUL sur un document fiscal. On
    rend donc le reste, et on nomme le manque là où il se produit.
    """
    if x is None:
        return "—"
    if isinstance(x, Undefined):
        nom = getattr(x, "_undefined_name", None) or "?"
        _avertir("Liasse : champ absent du modèle — %s", nom)
        return f"⚠ champ absent : {nom}"
    try:
        return f"{x:,.2f} €".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        _avertir("Liasse : valeur non formatable — %r", x)
        return f"⚠ valeur inattendue : {x!r}"
