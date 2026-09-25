# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Routes web du suivi des dépôts.

Branchées sur l'application par `enregistrer_routes(app, ctx)`, appelée
par `routes.enregistrer_tous` : le routeur principal ne nomme pas ce
module. La règle vit dans `depots` ; ici, on ne
fait que lire le formulaire, appeler, et rediriger vers la page Liasse avec
le message de réussite ou de refus.

Les gardes d'origine (`gardes_http._garde_origine`) sont des
`before_request` globales : elles couvrent ces routes sans rien ajouter.
"""
from __future__ import annotations

from flask import redirect, request, url_for

import depots


def enregistrer_routes(app, ctx) -> None:
    """`ctx.conn` ouvre la base du dossier actif ; `ctx.annee_param` lit
    l'année demandée — ce sont les fonctions du routeur, pour viser le même
    dossier que toutes les autres pages (bac à sable compris)."""
    conn, annee_param = ctx.conn, ctx.annee_param

    def _retour(annee, **msg):
        return redirect(url_for("liasse_page", annee=annee, _anchor="depots",
                                **msg))

    @app.route("/depots/enregistrer", methods=["POST"])
    def depot_enregistrer():
        c = conn()
        annee = annee_param(c)
        f = request.form
        try:
            depots.enregistrer(
                c, annee=annee, type=f.get("type", ""),
                nature=f.get("nature", ""), date_depot=f.get("date_depot", ""),
                reference=f.get("reference"), note=f.get("note"))
            return _retour(annee, ok="Dépôt enregistré.")
        except ValueError as exc:
            return _retour(annee, err=str(exc))
        finally:
            c.close()

    @app.route("/depots/<int:depot_id>/supprimer", methods=["POST"])
    def depot_supprimer(depot_id):
        c = conn()
        annee = annee_param(c)
        try:
            r = depots.supprimer(c, depot_id)
            return _retour(r["annee"], ok=depots.message_suppression(r))
        except ValueError as exc:
            return _retour(annee, err=str(exc))
        finally:
            c.close()

    # Lectures appelées depuis les gabarits (pages.py reste sans logique :
    # il affiche ce que ces fonctions renvoient).
    def _etat(annee):
        c = conn()
        try:
            return depots.etat(c, annee)
        finally:
            c.close()

    def _resume(annee):
        c = conn()
        try:
            return depots.resume(c, annee)
        finally:
            c.close()

    app.jinja_env.globals["depots_etat"] = _etat
    app.jinja_env.globals["depots_resume"] = _resume
