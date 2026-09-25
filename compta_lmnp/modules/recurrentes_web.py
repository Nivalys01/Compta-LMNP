# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Routes web des charges récurrentes.

Branchées par `enregistrer_routes(app, …)`, comme `depots_web` : le routeur
principal ne reçoit que l'appel. La règle vit dans `recurrentes` et
`echeancier` ; ici, on lit le formulaire, on appelle, on redirige avec le
message de réussite ou de refus. Les gardes d'origine (`gardes_http`) sont
globales et couvrent ces routes.

Page `/recurrentes` sans onglet propre : la fonction prolonge la saisie, on
y arrive depuis la page Saisie.
"""
from __future__ import annotations

from datetime import date

from flask import redirect, render_template_string, request, url_for

import echeancier
import gabarits
import recurrentes
from pages import PAGE_RECURRENTES


def _date(valeur: str | None, defaut: date) -> date:
    try:
        return date.fromisoformat(valeur) if valeur else defaut
    except ValueError:
        return defaut


def _ligne_vue(ligne: echeancier.Ligne) -> dict:
    e = ligne.echeance
    return {"cle": ligne.cle, "date": e.date.strftime("%d/%m/%Y"),
            "libelle": e.libelle, "source_id": e.source_id,
            "montant": round(sum(op["montant"] for op in e.operations), 2),
            "statut": ligne.statut,
            "statut_libelle": echeancier.LIBELLES_STATUT[ligne.statut],
            "motif": ligne.motif, "doublons": ligne.doublons,
            "operations_liees": ligne.operations_liees,
            "alertes": e.alertes, "cochee": ligne.cochee_par_defaut}


def enregistrer_routes(app, *, conn, annee_param, base, annees) -> None:
    """`conn`, `annee_param`, `base` et `annees` sont les fonctions du
    routeur : même dossier actif (bac à sable compris), même mise en page."""

    def _retour(annee, ancre="apercu", **params):
        return redirect(url_for("recurrentes_page", annee=annee,
                                _anchor=ancre, **params))

    @app.route("/recurrentes")
    def recurrentes_page():
        c = conn()
        try:
            annee = annee_param(c)
            defaut_du, defaut_au = recurrentes.periode_par_defaut(c, annee)
            du = _date(request.args.get("du"), defaut_du)
            au = _date(request.args.get("au"), defaut_au)
            edition = None
            if request.args.get("modele", type=int):
                try:
                    edition = recurrentes.modele(
                        c, request.args.get("modele", type=int))
                except ValueError:
                    edition = None
            lignes = recurrentes.apercu(c, du, au) if du <= au else []
            tous = gabarits.tous(c)
            body = render_template_string(
                PAGE_RECURRENTES, annee=annee, du=du.isoformat(),
                au=au.isoformat(), modeles=recurrentes.lister(c),
                edition=edition,
                lignes=[_ligne_vue(x) for x in lignes],
                a_generer=sum(1 for x in lignes
                              if x.statut == echeancier.A_GENERER),
                admis=[(k, tous[k]["libelle"])
                       for k in recurrentes.GABARITS_ADMIS if k in tous],
                aides={tous[k]["libelle"]: t
                       for k, t in recurrentes.AIDES.items() if k in tous},
                biens=c.execute("SELECT id, libelle FROM bien ORDER BY id"
                                ).fetchall(),
                periodicites=list(recurrentes.PERIODICITES),
                fenetre=echeancier.FENETRE_DOUBLON_JOURS,
                aujourd_hui=echeancier._aujourd_hui().strftime("%d/%m/%Y"))
            return base(body, active="saisie", annee=annee, annees=annees(c),
                        flash_ok=request.args.get("ok", ""),
                        flash_err=request.args.get("err", ""),
                        flash_warn=request.args.get("warn", ""))
        finally:
            c.close()

    @app.route("/recurrentes/modele", methods=["POST"])
    def recurrentes_modele():
        c = conn()
        annee = annee_param(c)
        f = request.form
        champs = {k: f.get(k) for k in ("type", "bien_id", "montant",
                                        "periodicite", "jour", "date_debut",
                                        "date_fin", "libelle", "tiers")}
        champs["date_fin"] = champs["date_fin"] or None
        try:
            mid = f.get("id", type=int)
            if mid:
                recurrentes.modifier(c, mid, **champs)
                ok = (f"Modèle n° {mid} modifié. Les opérations déjà générées "
                      "ne changent pas.")
            else:
                mid = recurrentes.creer(c, **champs)
                ok = f"Modèle n° {mid} créé."
            return _retour(annee, ancre="modeles", ok=ok)
        except ValueError as exc:
            return _retour(annee, ancre="modeles", err=str(exc),
                           modele=f.get("id", ""))
        finally:
            c.close()

    @app.route("/recurrentes/<int:modele_id>/etat", methods=["POST"])
    def recurrentes_etat(modele_id):
        c = conn()
        annee = annee_param(c)
        actif = request.form.get("actif") == "1"
        try:
            recurrentes.activer(c, modele_id, actif)
            return _retour(annee, ancre="modeles",
                           ok=f"Modèle n° {modele_id} "
                              + ("repris." if actif else "suspendu."))
        except ValueError as exc:
            return _retour(annee, ancre="modeles", err=str(exc))
        finally:
            c.close()

    @app.route("/recurrentes/<int:modele_id>/supprimer", methods=["POST"])
    def recurrentes_supprimer(modele_id):
        c = conn()
        annee = annee_param(c)
        try:
            r = recurrentes.supprimer(c, modele_id)
            return _retour(annee, ancre="modeles", ok=(
                f"Modèle n° {modele_id} supprimé. Ses "
                f"{r['operations_conservees']} opération(s) déjà générée(s) "
                "sont conservées."))
        except ValueError as exc:
            return _retour(annee, ancre="modeles", err=str(exc))
        finally:
            c.close()

    @app.route("/recurrentes/depuis-operation/<int:operation_id>",
               methods=["POST"])
    def recurrentes_depuis_operation(operation_id):
        c = conn()
        annee = annee_param(c)
        try:
            mid = recurrentes.depuis_operation(c, operation_id)
            return _retour(annee, ancre="modeles", modele=mid, ok=(
                f"Modèle n° {mid} créé depuis l'opération (mensuel, à partir "
                "de sa date). Vérifiez la périodicité et le jour, puis "
                "enregistrez."))
        except ValueError as exc:
            return redirect(url_for("saisie", annee=annee, err=str(exc)))
        finally:
            c.close()

    @app.route("/recurrentes/generer", methods=["POST"])
    def recurrentes_generer():
        c = conn()
        annee = annee_param(c)
        f = request.form
        du = _date(f.get("du"), date(annee, 1, 1))
        au = _date(f.get("au"), date(annee, 12, 31))
        periode = {"du": du.isoformat(), "au": au.isoformat()}
        try:
            r = recurrentes.generer(c, du, au, set(f.getlist("retenir")),
                                    ecarter=set(f.getlist("ecarter")))
            return _retour(annee, ok=recurrentes.message_generation(r),
                           **periode)
        except (ValueError, echeancier.LotAnnule) as exc:
            return _retour(annee, err=str(exc), **periode)
        finally:
            c.close()

    @app.route("/recurrentes/retablir", methods=["POST"])
    def recurrentes_retablir():
        c = conn()
        annee = annee_param(c)
        periode = {k: request.form.get(k, "") for k in ("du", "au")}
        try:
            echeancier.retablir(c, request.form.get("cle", ""))
            return _retour(annee, ok="Échéance rétablie : elle est de nouveau "
                                     "proposée.", **periode)
        except ValueError as exc:
            return _retour(annee, err=str(exc), **periode)
        finally:
            c.close()

    def _resume(annee):
        c = conn()
        try:
            return recurrentes.resume(c, annee)
        finally:
            c.close()

    app.jinja_env.globals["recurrentes_resume"] = _resume
    # Le bouton ↻ de la page Saisie n'apparaît que sur une charge admise.
    app.jinja_env.globals["recurrents_admis"] = recurrentes.GABARITS_ADMIS
