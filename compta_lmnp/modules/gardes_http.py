# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Gardes d'ENTRÉE HTTP : ce qui est refusé avant que la requête n'existe.

Deux barrières, dans cet ordre, et l'ordre est la moitié du sujet :

1. **Le nom d'hôte.** Se lier à 127.0.0.1 restreint l'interface réseau, pas
   les noms qui résolvent vers elle.
2. **L'origine d'une écriture.** Une fois l'hôte digne de confiance, on peut
   enfin comparer `Origin` à `Host` — ce que la garde d'origine faisait déjà,
   mais sur une référence que le client fournissait lui-même.

Elles sont sorties de `app.py` parce qu'aucune ne dépend de lui : ni base, ni
dossier actif, ni liasse. Elles s'enregistrent par `enregistrer(app)`, appelé
AVANT tout autre `before_request` — Flask les exécute dans l'ordre de
déclaration, et son filtrage `TRUSTED_HOSTS` n'intervient qu'au routage.
"""
from __future__ import annotations

from flask import request

# Renseigné par enregistrer() : évite d'importer l'application, donc un cycle.
_journal = None


# ── Hôtes acceptés ────────────────────────────────────────────────────────
#
# Se lier à 127.0.0.1 restreint l'INTERFACE RÉSEAU, pas les NOMS D'HÔTE qui
# résolvent vers elle. N'importe quel domaine peut pointer sur 127.0.0.1 :
# c'est le principe du DNS rebinding. Le serveur acceptait alors le `Host`
# annoncé, et `_garde_origine` comparait `Origin` à ce même `Host` — un
# attaquant maîtrisant les deux les faisait coïncider. Reproduit en passe T :
# GET 200, POST 302, et un dossier réellement créé sous `audit.invalid`.
#
# La leçon est celle des autres gardes de ce projet : une garde qui tire sa
# référence de ce qu'elle doit contrôler ne contrôle rien.
_HOTES_AUTORISES = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


def _hote_sans_port(entete: str) -> str:
    """« 127.0.0.1:5000 » -> « 127.0.0.1 » ; « [::1]:5000 » -> « [::1] »."""
    valeur = (entete or "").strip().lower()
    if valeur.startswith("["):                   # IPv6 littéral
        fin = valeur.find("]")
        return valeur[:fin + 1] if fin != -1 else valeur
    return valeur.rsplit(":", 1)[0] if ":" in valeur else valeur


# Ce hook est enregistré AVANT tous les autres, et c'est délibéré : Flask
# exécute les `before_request` dans l'ordre de déclaration, et son propre
# filtrage TRUSTED_HOSTS intervient au ROUTAGE — donc après eux. Un hôte
# hostile atteindrait sinon la migration et la garde de version avant d'être
# rejeté.
def _garde_hote():
    recu = _hote_sans_port(request.headers.get("Host", ""))
    if recu and recu not in _HOTES_AUTORISES:
        _journal.warning("Hôte refusé — %s %s (Host: %s)",
                           request.method, request.path, recu)
        return (
            "Requête refusée : nom d'hôte non autorisé.\n\n"
            f"Hôte annoncé : {recu}\n"
            "Hôtes acceptés : localhost, 127.0.0.1, [::1]\n\n"
            "Ce logiciel ne s'utilise que depuis la machine où il tourne. "
            "Si vous voyez ce message, une page web a peut-être tenté de "
            "joindre votre comptabilité par un domaine détourné.",
            403, {"Content-Type": "text/plain; charset=utf-8"})
    return None


# Méthodes qui CHANGENT l'état. Une lecture forgée ne coûte rien ; une
# écriture forgée peut clôturer un exercice ou restaurer une sauvegarde.
_METHODES_ECRITURE = {"POST", "PUT", "PATCH", "DELETE"}


def _hote(url: str) -> str:
    """« http://localhost:5000/x » -> « http://localhost:5000 »."""
    from urllib.parse import urlsplit
    p = urlsplit(url or "")
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


def _garde_origine():
    """Refuse une écriture dont l'ORIGINE n'est pas le logiciel lui-même.

    Le modèle de menace reposait sur `host="127.0.0.1"` — « l'application
    n'est jamais exposée au réseau local ». C'est exact pour le réseau et
    SANS EFFET pour le navigateur : toute page ouverte dans le même
    navigateur pouvait poster ici. Reproduit avant correctif — un POST sans
    cookie, sans Referer et sans jeton clôturait l'exercice.

    Deux aggravations le rendaient pire qu'un CSRF ordinaire. `samesite=Lax`
    empêche l'envoi du cookie `dossier` sur une requête inter-site, si bien
    que `_dossier_actif()` retombait sur PRINCIPAL : une requête forgée
    visait TOUJOURS la comptabilité réelle, jamais le bac à sable. Et les
    routes concernées remplacent la base, clôturent, annulent, cèdent —
    aucune ne demande de connaître les données de l'utilisateur.

    Règle retenue : une origine PRÉSENTE et différente est refusée ; une
    origine ABSENTE est acceptée. Ce second choix est délibéré — curl, la
    ligne de commande et le client de test n'envoient aucun de ces
    en-têtes, et les exiger transformerait le contrôle en obstacle sans
    rien gagner : un navigateur, lui, envoie TOUJOURS `Origin` sur un POST
    inter-site (« null » si la politique de référent le masque), donc
    l'attaque par formulaire caché est bien couverte.
    """
    if request.method not in _METHODES_ECRITURE:
        return None
    attendu = _hote(request.base_url)
    for entete in ("Origin", "Referer"):
        valeur = request.headers.get(entete)
        if not valeur:
            continue
        if _hote(valeur) != attendu:
            _journal.warning("Écriture refusée — %s %s depuis %s",
                               request.method, request.path, valeur)
            return (
                "Requête refusée : elle ne vient pas du logiciel.\n\n"
                f"Origine annoncée : {valeur}\n"
                f"Origine attendue : {attendu}\n\n"
                "Si vous lisiez cette page dans le logiciel, revenez à "
                "l'accueil et refaites l'action. Si vous ne comprenez pas "
                "ce message, ne refaites rien : une autre page de votre "
                "navigateur a peut-être tenté d'agir sur votre "
                "comptabilité.", 403, {"Content-Type": "text/plain; charset=utf-8"})
        return None                     # origine présente et conforme
    return None                         # aucune origine annoncée


def enregistrer(app) -> None:
    """Branche les gardes sur l'application, et fixe les hôtes de confiance.

    `TRUSTED_HOSTS` est la barrière de Flask, posée au routage ; les deux
    hooks ci-dessous en sont la version applicative, posée avant tout effet
    de bord. Les deux, parce que la documentation de Flask précise que les
    `before_request` restent appelés lors d'un rejet de routage : se reposer
    sur le seul `TRUSTED_HOSTS` laisserait tourner ce qui se trouve en amont.
    """
    global _journal
    _journal = app.logger
    app.config["TRUSTED_HOSTS"] = sorted(_HOTES_AUTORISES)
    app.before_request(_garde_hote)
    app.before_request(_garde_origine)
