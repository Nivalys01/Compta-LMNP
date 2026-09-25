# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Routes web de l'onglet Emprunts.

Branchées par `enregistrer_routes(app, ctx)`, appelée par
`routes.enregistrer_tous`. La règle vit dans `emprunts` et `echeancier` ;
ici, on lit le formulaire, on appelle, on redirige avec le message de
réussite ou de refus. Les gardes d'origine (`gardes_http`) sont globales
et couvrent ces routes.

L'onglet Immobilisations affiche le même tableau, en lecture seule, par
`emprunts_du_bien` (globale Jinja posée ici) : une seule lecture, aucune
copie.
"""
from __future__ import annotations

import io
from datetime import date

from flask import redirect, render_template_string, request, send_file, url_for

import echeancier
import emprunts
from pages import PAGE_EMPRUNTS


def _date(valeur: str | None, defaut: date) -> date:
    try:
        return date.fromisoformat(valeur) if valeur else defaut
    except ValueError:
        return defaut


def _periode_exercice(conn, annee: int) -> tuple[date, date]:
    row = conn.execute("SELECT date_debut, date_fin FROM exercice WHERE annee=?",
                       (annee,)).fetchone()
    if row:
        return date.fromisoformat(row[0]), date.fromisoformat(row[1])
    return date(annee, 1, 1), date(annee, 12, 31)


def _ligne_apercu(ligne: echeancier.Ligne) -> dict:
    e = ligne.echeance
    return {"cle": ligne.cle, "date": e.date.strftime("%d/%m/%Y"),
            "libelle": e.libelle, "rang": e.rang,
            "charges": round(sum(op["montant"] for op in e.operations), 2),
            "total": e.montant_total or 0.0,
            "statut": ligne.statut,
            "statut_libelle": echeancier.LIBELLES_STATUT[ligne.statut],
            "motif": ligne.motif, "doublons": ligne.doublons,
            "operations_liees": ligne.operations_liees,
            "alertes": e.alertes, "cochee": ligne.cochee_par_defaut}


def enregistrer_routes(app, ctx) -> None:
    conn, annee_param, base, annees = (ctx.conn, ctx.annee_param, ctx.base,
                                       ctx.annees)

    def _retour(annee, emprunt_id=None, ancre="liste", **params):
        if emprunt_id:
            params["emprunt"] = emprunt_id
        return redirect(url_for("emprunts_page", annee=annee, _anchor=ancre,
                                **params))

    @app.route("/emprunts")
    def emprunts_page():
        c = conn()
        try:
            annee = annee_param(c)
            liste = emprunts.lister(c)
            choisi = request.args.get("emprunt", type=int)
            if choisi is None and liste:
                choisi = liste[0]["id"]
            vue = None
            if choisi is not None:
                try:
                    vue = emprunts.vue(c, choisi)
                except ValueError:
                    vue = None
            defaut_du, defaut_au = _periode_exercice(c, annee)
            du = _date(request.args.get("du"), defaut_du)
            au = _date(request.args.get("au"), defaut_au)
            lignes = (emprunts.apercu(c, du, au) if liste and du <= au
                      else [])
            body = render_template_string(
                PAGE_EMPRUNTS, annee=annee, emprunts=liste, vue=vue,
                choisi=choisi, du=du.isoformat(), au=au.isoformat(),
                lignes=[_ligne_apercu(x) for x in lignes],
                a_generer=sum(1 for x in lignes
                              if x.statut == echeancier.A_GENERER),
                biens=c.execute("SELECT id, libelle FROM bien ORDER BY id"
                                ).fetchall(),
                periodicites=list(emprunts.PERIODICITES),
                aide_taux=emprunts.AIDE_TAUX,
                rappel=emprunts.RAPPEL_CHARGES,
                aide_deblocages=emprunts.AIDE_DEBLOCAGES,
                colonnes_csv=" ; ".join(emprunts.COLONNES_CSV),
                fenetre=echeancier.FENETRE_DOUBLON_JOURS,
                eur=emprunts.euros_fr,
                aujourd_hui=echeancier._aujourd_hui().strftime("%d/%m/%Y"))
            return base(body, active="emprunts", annee=annee, annees=annees(c),
                        flash_ok=request.args.get("ok", ""),
                        flash_err=request.args.get("err", ""),
                        flash_warn=request.args.get("warn", ""))
        finally:
            c.close()

    @app.route("/emprunts/creer", methods=["POST"])
    def emprunts_creer():
        c = conn()
        annee = annee_param(c)
        f = request.form
        try:
            eid = emprunts.creer(c, **{k: f.get(k) for k in (
                "bien_id", "preteur", "reference", "capital", "taux",
                "nb_echeances", "periodicite", "date_deblocage",
                "date_premiere_echeance", "assurance")})
            return _retour(annee, eid, ancre="tableau", ok=(
                f"Emprunt n° {eid} créé, tableau calculé. Comparez-le au "
                "tableau de la banque : c'est lui qui fait foi."))
        except ValueError as exc:
            return _retour(annee, ancre="creation", err=str(exc))
        finally:
            c.close()

    @app.route("/emprunts/<int:emprunt_id>/supprimer", methods=["POST"])
    def emprunts_supprimer(emprunt_id):
        c = conn()
        annee = annee_param(c)
        try:
            emprunts.supprimer(c, emprunt_id)
            return _retour(annee, ok=f"Emprunt n° {emprunt_id} supprimé.")
        except ValueError as exc:
            return _retour(annee, emprunt_id, err=str(exc))
        finally:
            c.close()

    @app.route("/emprunts/<int:emprunt_id>/ligne", methods=["POST"])
    def emprunts_ligne(emprunt_id):
        c = conn()
        annee = annee_param(c)
        f = request.form
        try:
            r = emprunts.remplacer_ligne(
                c, emprunt_id, f.get("rang", type=int) or 0,
                date_echeance=f.get("date_echeance"), capital=f.get("capital"),
                interets=f.get("interets"), assurance=f.get("assurance"))
            ok = f"Échéance n° {f.get('rang')} remplacée."
            if r["recalculees"]:
                ok += (f" Les {r['recalculees']} échéance(s) calculée(s) "
                       "suivante(s) ont été recalculées.")
            warn = ""
            if r["ecart_interets"] is not None:
                warn = (f"Intérêts saisis différents de capital restant dû × "
                        f"taux ({emprunts.euros_fr(r['ecart_interets'])} €) : "
                        "accepté, la banque fait foi.")
            return _retour(annee, emprunt_id, ancre="tableau", ok=ok,
                           warn=warn)
        except ValueError as exc:
            return _retour(annee, emprunt_id, ancre="tableau", err=str(exc))
        finally:
            c.close()

    @app.route("/emprunts/<int:emprunt_id>/importer", methods=["POST"])
    def emprunts_importer(emprunt_id):
        c = conn()
        annee = annee_param(c)
        fichier = request.files.get("tableau")
        try:
            if not fichier or not fichier.filename:
                raise ValueError("Choisissez le fichier CSV du tableau de la "
                                 "banque.")
            r = emprunts.importer_csv(c, emprunt_id, fichier.read())
            ok = (f"Tableau de la banque importé : {r['nb']} échéance(s) à "
                  f"partir de la n° {r['premier_rang']}.")
            alertes = []
            if r["ecarts_interets"]:
                alertes.append(
                    f"{r['ecarts_interets']} échéance(s) dont les intérêts "
                    "diffèrent de capital restant dû × taux : acceptées, la "
                    "banque fait foi (marquées dans le tableau).")
            if r["reliquat"]:
                alertes.append(emprunts.alerte_reliquat(r["reliquat"]))
            warn = " ".join(alertes)
            return _retour(annee, emprunt_id, ancre="tableau", ok=ok,
                           warn=warn)
        except ValueError as exc:
            return _retour(annee, emprunt_id, ancre="banque", err=str(exc))
        finally:
            c.close()

    @app.route("/emprunts/<int:emprunt_id>/export.csv")
    def emprunts_export(emprunt_id):
        c = conn()
        try:
            texte = emprunts.exporter_csv(c, emprunt_id)
        except ValueError as exc:
            return redirect(url_for("emprunts_page", err=str(exc)))
        finally:
            c.close()
        return send_file(io.BytesIO(texte.encode("utf-8-sig")),
                         mimetype="text/csv", as_attachment=True,
                         download_name=f"emprunt-{emprunt_id}-tableau.csv")

    @app.route("/emprunts/generer", methods=["POST"])
    def emprunts_generer():
        c = conn()
        annee = annee_param(c)
        f = request.form
        du = _date(f.get("du"), date(annee, 1, 1))
        au = _date(f.get("au"), date(annee, 12, 31))
        periode = {"du": du.isoformat(), "au": au.isoformat()}
        try:
            r = emprunts.generer(c, du, au, set(f.getlist("retenir")),
                                 ecarter=set(f.getlist("ecarter")))
            return _retour(annee, f.get("emprunt"), ancre="apercu",
                           ok=emprunts.message_generation(r), **periode)
        except (ValueError, echeancier.LotAnnule) as exc:
            return _retour(annee, f.get("emprunt"), ancre="apercu",
                           err=str(exc), **periode)
        finally:
            c.close()

    @app.route("/emprunts/retablir", methods=["POST"])
    def emprunts_retablir():
        c = conn()
        annee = annee_param(c)
        periode = {k: request.form.get(k, "") for k in ("du", "au")}
        try:
            echeancier.retablir(c, request.form.get("cle", ""))
            return _retour(annee, request.form.get("emprunt"), ancre="apercu",
                           ok="Échéance rétablie : elle est de nouveau "
                              "proposée, et sa ligne du tableau redevient "
                              "modifiable.", **periode)
        except ValueError as exc:
            return _retour(annee, request.form.get("emprunt"), ancre="apercu",
                           err=str(exc), **periode)
        finally:
            c.close()

    def _du_bien(bien_id):
        """Pour l'onglet Immobilisations : les vues des emprunts d'un bien,
        lues comme dans l'onglet Emprunts."""
        c = conn()
        try:
            return [emprunts.vue(c, e["id"])
                    for e in emprunts.lister(c, bien_id=bien_id)]
        finally:
            c.close()

    app.jinja_env.globals["emprunts_du_bien"] = _du_bien
    app.jinja_env.globals["eur"] = emprunts.euros_fr
    app.jinja_env.globals["alerte_reliquat"] = emprunts.alerte_reliquat
