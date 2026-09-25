# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Routes de l'onglet Nouvel exercice : ouverture (avec reprise des
à-nouveaux) et reprise d'exercices depuis leurs FEC, un seul ou plusieurs
analysés d'abord.

Déplacées d'`app.py` à l'identique (8.58.0) : seule l'indentation a changé,
les fonctions du routeur étant reçues par le contexte sous leurs noms
d'origine. Les règles vivent dans `reprise`, `rejeu_fec` et `migration_fec`.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import date

from flask import redirect, render_template_string, request, url_for

import migration_fec
import rejeu_fec
import reprise
import veille_fiscale
from formulaires import form_int as _form_int
from pages import PAGE_EX_NOUVEAU


def enregistrer_routes(app, ctx) -> None:
    """Branche les routes de l'onglet sur l'application (voir `routes`)."""
    _conn, _annee_param, _annees, _base, _dossier_imports = (
        ctx.conn, ctx.annee_param, ctx.annees, ctx.base, ctx.dossier_imports)

    @app.route("/exercice/nouveau")
    def exercice_nouveau():
        return _page_exercice_nouveau(None)


    def _page_exercice_nouveau(conn_ouverte, analyse=None):
        """Rend la page. `analyse` porte le résultat d'une analyse
        multi-FEC, qui doit s'afficher SANS redirection — sinon le
        résultat serait perdu."""
        del conn_ouverte
        conn   = _conn()
        annee  = _annee_param(conn)
        annees = _annees(conn)
        exercices = conn.execute(
            "SELECT * FROM exercice ORDER BY annee DESC"
        ).fetchall()
        annee_suggere = (max(e["annee"] for e in exercices) + 1) if exercices else date.today().year
        prev_ouvert   = next(
            (e["annee"] for e in exercices if e["statut"] == "ouvert"), None
        )
        reprise_possible = any(
            e["annee"] == annee_suggere - 1 and e["statut"] == "clos" for e in exercices
        )
        conn.close()

        conn2 = _conn()
        veille_due = veille_fiscale.veille_a_refaire(conn2)
        derniere = veille_fiscale.derniere_veille(conn2)
        conn2.close()
        body = render_template_string(PAGE_EX_NOUVEAU,
            annee=annee, exercices=exercices,
            annee_suggere=annee_suggere, prev_ouvert=prev_ouvert,
            reprise_possible=reprise_possible, analyse=analyse,
            veille_due=veille_due, derniere_veille=derniere)
        return _base(body, active="exercice_nouveau", annee=annee, annees=annees,
                     flash_ok=request.args.get("ok",""),
                     flash_err=request.args.get("err",""))


    @app.route("/exercice/ouvrir", methods=["POST"])
    def exercice_ouvrir():
        conn = _conn()
        try:
            a    = _form_int("annee")
            if a is None:
                raise ValueError("Année d'exercice invalide.")
            deb  = request.form.get("date_debut", "")
            fin  = request.form.get("date_fin", "")
            exis = conn.execute("SELECT annee FROM exercice WHERE annee=?", (a,)).fetchone()
            if exis:
                raise ValueError(f"L'exercice {a} existe déjà.")
            # UN SEUL GESTE. L'exercice était créé et committé AVANT que la
            # reprise ne soit tentée : un refus laissait un exercice vide, alors
            # que le message invitait à recommencer après clôture. Ouvrir avec
            # reprise aboutit, ou ne laisse rien (constat Q-11).
            reprise_demandee = request.form.get("reprise") == "1"
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO exercice (annee, date_debut, date_fin, statut) VALUES (?,?,?,'ouvert')",
                (a, deb, fin)
            )
            msg = f"Exercice {a} ouvert ({deb} → {fin})."
            if reprise_demandee:
                info = reprise.construire_an_interne(conn, a, commit=False)
                d, c_ = reprise.controle_equilibre(conn, a)
                if abs(d - c_) > 0.005:
                    raise ValueError("À-nouveaux déséquilibrés — reprise annulée.")
                msg += (f" À-nouveaux repris depuis {info['annee_source']} : "
                        f"{info['nb_comptes']} comptes, résultat reporté "
                        f"{info['resultat_reporte']:.2f} € (affecté au compte exploitant).")
            conn.commit()
            if veille_fiscale.veille_a_refaire(conn):
                msg += (" Pensez à votre veille fiscale avant de saisir : "
                        "voir le menu « Veille fiscale ».")
            conn.close()
            return redirect(url_for("exercice_nouveau", annee=a, ok=msg))
        except Exception as exc:
            conn.rollback()
            conn.close()
            return redirect(url_for("exercice_nouveau", err=str(exc)))


    @app.route("/exercice/analyser-fec", methods=["POST"])
    def exercice_analyser_fec():
        """Analyse PLUSIEURS FEC sans rien écrire.

        Deux temps volontairement séparés : une migration est irréversible en
        pratique (on ne défait pas trois exercices d'un clic), et l'utilisateur
        doit voir ce que le logiciel a compris — l'ordre déduit, les jonctions,
        les dotations — AVANT de s'engager.
        """
        fichiers = [f for f in request.files.getlist("fecs") if f and f.filename]
        if not fichiers:
            return redirect(url_for("exercice_nouveau",
                                    err="Sélectionnez au moins un fichier FEC."))
        conn = _conn()
        try:
            jeton = uuid.uuid4().hex
            dossier = os.path.join(_dossier_imports(), jeton)
            os.makedirs(dossier, exist_ok=True)
            chemins = []
            for n, f in enumerate(fichiers):
                c = os.path.join(dossier, f"{n:02d}.txt")
                f.save(c)
                chemins.append(c)
            ordre = migration_fec.ordonner(chemins)
            for x, f in zip(ordre, [None] * len(ordre)):
                del f
            noms = {c: f.filename for c, f in zip(chemins, fichiers)}
            for x in ordre:
                x["nom"] = noms.get(x["chemin"], "")
                x["dotations"] = migration_fec.dotations_du_fec(x["chemin"])
            deja = {r[0] for r in conn.execute("SELECT annee FROM exercice")}
            for x in ordre:
                if x["annee"] and x["annee"] in deja:
                    x["erreurs"].append(
                        f"l'exercice {x['annee']} existe déjà dans ce dossier : "
                        "il ne sera pas repris.")
            obs = (migration_fec.controler_jonctions(ordre)
                   + migration_fec.controler_amortissements(conn, ordre))
            reprenables = sum(1 for x in ordre if x["annee"] and not x["erreurs"])
            analyse = {"fichiers": ordre, "observations": obs,
                       "jeton": jeton, "reprenables": reprenables}
            return _page_exercice_nouveau(None, analyse=analyse)
        except Exception as exc:
            return redirect(url_for("exercice_nouveau", err=str(exc)))
        finally:
            conn.close()


    @app.route("/exercice/reprendre-fec-multi", methods=["POST"])
    def exercice_reprendre_fec_multi():
        """Rejoue les exercices analysés, DU PLUS ANCIEN AU PLUS RÉCENT.

        L'ordre est imposé par les données : rejouer 2025 avant 2023
        produirait des à-nouveaux absurdes, et l'utilisateur n'a aucune raison
        de connaître cette contrainte.
        """
        jeton = request.form.get("jeton", "")
        if not re.fullmatch(r"[0-9a-f]{32}", jeton):
            return redirect(url_for("exercice_nouveau",
                                    err="Session d'analyse expirée — recommencez."))
        dossier = os.path.join(_dossier_imports(), jeton)
        if not os.path.isdir(dossier):
            return redirect(url_for("exercice_nouveau",
                                    err="Session d'analyse expirée — recommencez."))
        conn = _conn()
        echoue = False
        try:
            chemins = [os.path.join(dossier, n) for n in sorted(os.listdir(dossier))]
            ordre = migration_fec.ordonner(chemins)
            deja = {r[0] for r in conn.execute("SELECT annee FROM exercice")}
            faits, ignores = [], []
            for x in ordre:
                a = x["annee"]
                if not a or a in deja:
                    ignores.append(str(a or "?"))
                    continue
                conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, "
                             "statut) VALUES (?,?,?,'ouvert')",
                             (a, f"{a}-01-01", f"{a}-12-31"))
                res = rejeu_fec.rejouer(conn, x["chemin"], a, commit=False)
                faits.append(f"{a} ({res['ecritures']} écritures)")
                deja.add(a)
            conn.commit()
            if not faits:
                raise ValueError("Aucun exercice repris : tous étaient déjà "
                                 "présents ou illisibles.")
            msg = ("Exercices repris du plus ancien au plus récent : "
                   + ", ".join(faits) + ".")
            if ignores:
                msg += f" Ignorés : {', '.join(ignores)}."
            msg += (" Vérifiez la balance de chaque exercice, puis clôturez-les "
                    "dans l'ordre.")
            return redirect(url_for("exercice_nouveau", ok=msg))
        except Exception as exc:
            # TOUT OU RIEN, et la PRÉPARATION EST CONSERVÉE. Chaque rejeu
            # committait le sien : une reprise de deux fichiers qui échouait sur
            # le second laissait durablement le premier exercice, tandis que le
            # `finally` effaçait le dossier des fichiers téléversés. L'action
            # globale se terminait en erreur, l'état était partiel, et de quoi
            # recommencer avait disparu (constat Q-09).
            conn.rollback()
            echoue = True
            return redirect(url_for("exercice_nouveau", err=(
                f"Reprise interrompue : {exc}\n\nAucun exercice n'a été repris "
                "— la base est dans l'état où elle était. Vos fichiers restent "
                "chargés : corrigez celui qui est en cause, puis relancez "
                "l'analyse.")))
        finally:
            conn.close()
            if not echoue:
                import shutil
                shutil.rmtree(dossier, ignore_errors=True)


    @app.route("/exercice/reprendre-fec", methods=["POST"])
    def exercice_reprendre_fec():
        """Reprise d'un exercice complet depuis son FEC (migration depuis un
        prestataire de comptabilité LMNP) :
        exercice créé puis fichier rejoué écriture par écriture."""
        f = request.files.get("fec")
        a = _form_int("annee")
        if f is None or not f.filename or a is None:
            return redirect(url_for("exercice_nouveau",
                                    err="Année et fichier FEC requis."))
        conn = _conn()
        chemin = os.path.join(_dossier_imports(), uuid.uuid4().hex + ".txt")
        try:
            f.save(chemin)
            if conn.execute("SELECT 1 FROM exercice WHERE annee=?", (a,)).fetchone():
                raise ValueError(f"L'exercice {a} existe déjà : la reprise crée "
                                 "l'exercice, elle ne complète pas un exercice "
                                 "existant.")
            conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, "
                         "statut) VALUES (?,?,?,'ouvert')",
                         (a, f"{a}-01-01", f"{a}-12-31"))
            res = rejeu_fec.rejouer(conn, chemin, a)
            conn.commit()
            # Toute TRANSFORMATION du fichier source est annoncée. Une reprise
            # qui se dit réussie sans dire ce qu'elle a changé laisse croire que
            # le ré-export reproduira le fichier remis.
            ok = (f"Exercice {a} repris depuis le FEC : {res['ecritures']} "
                  f"écritures rejouées, {len(res['comptes_crees'])} compte(s) "
                  f"créé(s) depuis le fichier"
                  + (f", {res['normalisees']} ligne(s) à montant négatif "
                     f"normalisée(s) par équivalence comptable" if res.get("normalisees") else "")
                  + (". Les écritures ont été RENUMÉROTÉES de 1 à "
                     f"{res['ecritures']} (les numéros du fichier source se "
                     "répétaient d'un journal à l'autre, ou n'étaient pas "
                     "numériques) : conservez le FEC d'origine"
                     if res.get("renumerotees") else "")
                  + (". Libellé(s) de journal conservé(s) depuis le plan du "
                     f"logiciel — {'; '.join(res['journaux_renommes'])}"
                     if res.get("journaux_renommes") else "")
                  + ". Vérifiez la balance puis clôturez normalement.")
            return redirect(url_for("exercice_nouveau", annee=a, ok=ok))
        except Exception as exc:
            conn.rollback()
            return redirect(url_for("exercice_nouveau", err=f"Reprise refusée : {exc}"))
        finally:
            conn.close()
            if os.path.exists(chemin):
                os.remove(chemin)
