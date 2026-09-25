# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Lecture des champs de formulaire web, sans jamais lever.

Partagée par le routeur (`app.py`) et les modules de routes (`*_web.py`) :
un entier ou un montant mal tapé rend une valeur par défaut, et c'est la
couche métier qui renvoie le message clair. Déplacée d'`app.py` telle
quelle lors de l'extraction des routes (8.58.0).
"""
from __future__ import annotations

import math

from flask import request


def form_int(nom: str, defaut=None):
    """Lit un entier de formulaire SANS jamais lever : renvoie `defaut` si le
    champ est absent, vide ou non entier. Évite les erreurs 500 sur saisie
    malformée — la couche métier renverra un message clair si `defaut` est
    invalide en aval."""
    brut = (request.form.get(nom) or "").strip()
    try:
        return int(brut)
    except (TypeError, ValueError):
        return defaut


def form_float(nom: str, defaut=None):
    """Idem pour un décimal. Accepte la virgule française (« 795,50 »).

    `float()` accepte aussi « nan », « inf » et « 1e400 » : trois mots que
    n'importe qui peut taper dans un champ de montant, et qui traversaient
    ensuite toutes les comparaisons de la couche métier sans jamais les
    faire échouer. Ce ne sont pas des montants — ils sont traités comme une
    saisie invalide, au même titre qu'un mot quelconque."""
    brut = (request.form.get(nom) or "").strip().replace(",", ".")
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        return defaut
    return valeur if math.isfinite(valeur) else defaut
