# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Routes de l'onglet Immobilisations : exploitant, biens, composants,
ventilation initiale, durées, suppression, reprise des amortissements
antérieurs, cession d'un bien.

Déplacées d'`app.py` à l'identique (8.58.0) : seule l'indentation a changé,
les fonctions du routeur étant reçues par le contexte sous leurs noms
d'origine. Les règles vivent dans `amortissement`, `operations`,
`plan_immo` et `cession`.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from flask import redirect, render_template_string, request, url_for

import amortissement
import cession
import operations
import plan_immo
from formulaires import form_float as _form_float
from formulaires import form_int as _form_int
from pages import PAGE_IMMO

# Comptes immobilisation disponibles (compte_immo → compte_amort ou None).
# La table vivait ICI, en dur, dans la couche web — une connaissance
# comptable logée dans la présentation, et dupliquée avec celle de liasse.py
# sans que l'une référence l'autre. Source unique désormais :
# modules/plan_immo.py (constat D2-05).
COMPTES_IMMO = plan_immo.pour_la_saisie()


def _annees_ouvertes(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT annee FROM exercice WHERE statut='ouvert' ORDER BY annee DESC"
    ).fetchall()
    return [r[0] for r in rows]


def enregistrer_routes(app, ctx) -> None:
    """Branche les routes de l'onglet sur l'application (voir `routes`)."""
    _conn, _annee_param, _annees, _base = (ctx.conn, ctx.annee_param,
                                           ctx.annees, ctx.base)

    @app.route("/immobilisations")
    def immobilisations():
        conn   = _conn()
        cession.assurer_schema(conn)          # colonnes/comptes de cession à la volée
        conn.commit()
        annee  = _annee_param(conn)
        annees = _annees(conn)
        exp    = conn.execute("SELECT * FROM exploitant LIMIT 1").fetchone()
        biens  = conn.execute("SELECT * FROM bien ORDER BY id").fetchall()
        compos = conn.execute("SELECT * FROM composant ORDER BY bien_id, id").fetchall()
        manque_amort = operations.amortissements_anterieurs_manquants(conn, annee)["total"]
        conn.close()

        amort_map = {num: amort for num, _, amort in COMPTES_IMMO}
        body = render_template_string(PAGE_IMMO,
            amort_anterieurs=manque_amort,
            ventilations={b["id"]: amortissement.ventilation_proposee(
                b["prix_total"] or 0.0, b["quote_part_terrain"])
                for b in biens
                if not any(c["bien_id"] == b["id"] for c in compos)},
            annee=annee, exploitant=exp, biens=biens, composants=compos,
            comptes_immo=COMPTES_IMMO,
            dedoublables=amortissement.POSTES_DEDOUBLABLES,
            amort=amort_map,
        )
        return _base(body, active="immobilisations", annee=annee, annees=annees,
                     flash_ok=request.args.get("ok",""),
                     flash_err=request.args.get("err",""),
                     flash_warn=request.args.get("warn",""))


    @app.route("/immobilisations/exploitant", methods=["POST"])
    def creer_exploitant():
        """Enregistre l'exploitant.

        Accessible depuis la page Immobilisations ET depuis la configuration
        initiale d'un dossier neuf : c'est là qu'un débutant la cherche, et
        l'y trouver évite de commencer par une page d'immobilisations vide
        (retour d'usage). Le paramètre `retour` dit où revenir.
        """
        conn  = _conn()
        annee = _annee_param(conn)
        retour = request.form.get("retour") or "immobilisations"
        try:
            conn.execute(
                "INSERT INTO exploitant (nom, siren, adresse) VALUES (?,?,?)",
                (request.form["nom"], request.form["siren"], request.form.get("adresse",""))
            )
            conn.commit()
            ouverts = _annees_ouvertes(conn)
            ok = (f"Dossier configuré au nom de « {request.form['nom']} ». "
                  f"L'exercice {ouverts[0]} est déjà OUVERT : vous pouvez "
                  "saisir immédiatement." if ouverts else
                  f"Exploitant « {request.form['nom']} » enregistré.")
        except Exception as exc:
            conn.close()
            return redirect(url_for(retour, annee=annee, err=str(exc)))
        conn.close()
        cible = "saisie" if retour == "saisie" else retour
        return redirect(url_for(cible, annee=annee, ok=ok))


    @app.route("/immobilisations/bien", methods=["POST"])
    def creer_bien():
        conn  = _conn()
        annee = _annee_param(conn)
        try:
            exp = conn.execute("SELECT id FROM exploitant LIMIT 1").fetchone()
            if not exp:
                raise ValueError("Créez d'abord un exploitant.")
            prix  = request.form.get("prix_total") or None
            qpt   = request.form.get("quote_part_terrain") or None
            dacq  = request.form.get("date_acquisition") or None
            conn.execute(
                "INSERT INTO bien (exploitant_id, libelle, adresse, date_acquisition, "
                "prix_total, quote_part_terrain) VALUES (?,?,?,?,?,?)",
                (exp[0], request.form["libelle"], request.form.get("adresse",""),
                 dacq, float(prix) if prix else None, float(qpt) if qpt else None)
            )
            conn.commit()
            ok = f"Bien « {request.form['libelle']} » créé."
        except Exception as exc:
            conn.close()
            return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
        conn.close()
        return redirect(url_for("immobilisations", annee=annee, ok=ok))


    @app.route("/immobilisations/composant", methods=["POST"])
    def creer_composant():
        conn  = _conn()
        annee = _annee_param(conn)
        try:
            bien_id  = _form_int("bien_id")
            if bien_id is None:
                raise ValueError("Bien non sélectionné.")
            duree    = amortissement.duree_valide(request.form.get("duree_annees", ""))
            amortissable = 1 if duree else 0

            cpt_immo = request.form["compte_immo"]
            # Résolution automatique du compte d'amortissement depuis le compte
            # d'immobilisation — par le plan, qui reconnaît aussi les
            # subdivisions à sept chiffres d'un cabinet.
            cpt_amort = plan_immo.compte_amortissement(cpt_immo) if amortissable else None
            # Un compte SANS contrepartie d'amortissement (le terrain) ne peut
            # pas porter de durée : le composant était accepté, puis la clôture
            # échouait sur « NOT NULL constraint failed: ligne.compte_num » —
            # message incompréhensible, et blocage total (constat d'usage).
            if amortissable and not cpt_amort:
                libelle_cpt = next((lib for num, lib, _ in COMPTES_IMMO
                                    if num == cpt_immo), cpt_immo)
                raise ValueError(
                    f"« {libelle_cpt} » n'est pas amortissable : laissez la "
                    "durée à 0. Le terrain ne se déprécie pas — c'est d'ailleurs "
                    "pour cela qu'il faut isoler sa quote-part du reste du prix. "
                    "Si vous vouliez amortir du bâti, choisissez « Bâtiment ».")

            dms = request.form.get("date_mise_service") or None
            conn.execute(
                "INSERT INTO composant (bien_id, code_immo, libelle, categorie, valeur_brute, "
                "duree_annees, date_mise_service, compte_immo, compte_amort, amortissable) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (bien_id, request.form.get("code_immo") or None, request.form["libelle"],
                 request.form.get("categorie",""), float(request.form["valeur_brute"]),
                 duree, dms, cpt_immo, cpt_amort, amortissable)
            )
            # Pas de commit ici : il vient après l'écriture d'acquisition, pour
            # que les deux tiennent ou tombent ensemble (constat Q-07).
            ok = f"Composant « {request.form['libelle']} » ajouté."
            # Alerte de cohérence AU MOMENT DE L'AJOUT : c'est là qu'elle sert,
            # pendant que l'utilisateur a le montant en tête.
            b = conn.execute("SELECT libelle, prix_total FROM bien WHERE id=?",
                             (bien_id,)).fetchone()
            if b and b["prix_total"]:
                total = conn.execute(
                    "SELECT COALESCE(SUM(valeur_brute),0) FROM composant "
                    "WHERE bien_id=?", (bien_id,)).fetchone()[0]
                depassement = round(total - b["prix_total"], 2)
                if depassement > 0.05 * b["prix_total"]:
                    ok += (f" ⚠ La somme des composants ({total:.2f} €) dépasse "
                           f"désormais de {depassement:.2f} € "
                           f"({depassement / b['prix_total'] * 100:.1f} %) le "
                           f"prix d'acquisition ({b['prix_total']:.2f} €). "
                           "Normal si vous immobilisez des travaux postérieurs ; "
                           "à vérifier s'il s'agit de la ventilation initiale.")

            # Écriture d'acquisition (débit 2xx / crédit 108000) sur l'exercice
            # ouvert — sinon le composant n'existe qu'en référentiel et le bilan
            # (2033-A) comme le FEC seraient faux. Désactivable pour une reprise
            # d'historique déjà portée par les à-nouveaux.
            if request.form.get("sans_ecriture") != "1":
                ouverts = _annees_ouvertes(conn)
                if not ouverts:
                    raise ValueError("Aucun exercice ouvert pour comptabiliser "
                                     "l'écriture d'acquisition.")
                cible = min(ouverts)
                date_op = dms if dms and int(dms[:4]) == cible else f"{cible}-01-01"
                res = operations.saisir_acquisition(
                    conn, compte_immo=cpt_immo,
                    montant=float(request.form["valeur_brute"]),
                    date_operation=date_op, libelle=request.form["libelle"],
                    exercice=cible)
                ok += (f" Écriture d'acquisition n°{res['ecriture_num']} "
                       f"générée sur {cible}.")
        except Exception as exc:
            # Le composant était committé AVANT l'écriture d'acquisition : une
            # date invalide laissait 12 000 € au référentiel sans écriture, et
            # l'erreur ne disait pas qu'une partie était enregistrée (Q-07).
            conn.rollback()
            conn.close()
            return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
        conn.commit()
        conn.close()
        return redirect(url_for("immobilisations", annee=annee, ok=ok))


    @app.route("/immobilisations/ventiler", methods=["POST"])
    def immo_ventiler():
        """
        Ventile le prix d'acquisition d'un bien en composants, en une fois.

        Ajouté après un constat d'usage : on pouvait empiler des composants
        sans qu'aucun lien ne soit fait avec le prix payé. Or c'est la
        ventilation qui donne au réel tout son intérêt — un bien saisi en bloc
        s'amortit sur la durée du gros œuvre, et le mobilier, qui devrait
        s'amortir en quelques années, s'étale sur des décennies.
        """
        conn = _conn()
        annee = _annee_param(conn)
        try:
            bien_id = _form_int("bien_id")
            bien = conn.execute("SELECT * FROM bien WHERE id=?",
                                (bien_id,)).fetchone()
            if bien is None:
                raise ValueError("Bien introuvable.")
            if conn.execute("SELECT COUNT(*) FROM composant WHERE bien_id=?",
                            (bien_id,)).fetchone()[0]:
                raise ValueError(
                    "Ce bien a déjà des composants : la ventilation initiale ne "
                    "s'utilise qu'une fois. Ajoutez les composants manquants "
                    "un par un ci-dessous, ou supprimez les lignes existantes "
                    "pour la refaire entièrement.")
            dms = request.form.get("date_mise_service") or bien["date_acquisition"]
            postes = amortissement.postes_ventilation(request.form)
            if not postes:
                raise ValueError("Aucun montant saisi : renseignez au moins un "
                                 "poste.")
            cree, total = 0, 0.0
            for poste in postes:
                duree = poste["duree"]
                cpt_amort = (plan_immo.compte_amortissement(poste["compte_immo"])
                             if duree else None)
                if duree and not cpt_amort:
                    raise ValueError(f"« {poste['libelle']} » ne s'amortit pas : "
                                     "laissez sa durée à 0.")
                conn.execute(
                    "INSERT INTO composant (bien_id, libelle, categorie, "
                    "valeur_brute, duree_annees, date_mise_service, compte_immo, "
                    "compte_amort, amortissable) VALUES (?,?,?,?,?,?,?,?,?)",
                    (bien_id, poste["libelle"], poste["categorie"],
                     poste["montant"], duree, dms, poste["compte_immo"],
                     cpt_amort, 1 if duree else 0))
                ouverts = _annees_ouvertes(conn)
                if request.form.get("sans_ecriture") != "1" and ouverts:
                    cible = min(ouverts)
                    date_op = (dms if dms and int(dms[:4]) == cible
                               else f"{cible}-01-01")
                    operations.saisir_acquisition(
                        conn, compte_immo=poste["compte_immo"],
                        montant=poste["montant"], date_operation=date_op,
                        libelle=poste["libelle"], exercice=cible, commit=False)
                cree += 1
                total = round(total + poste["montant"], 2)
            conn.commit()
            prix = bien["prix_total"] or 0.0
            alerte = ""
            if prix and abs(total - prix) > 0.05 * prix:
                alerte = (f" Attention : le total ventilé ({total:.2f} €) "
                          f"s'écarte de plus de 5 % du prix d'acquisition "
                          f"({prix:.2f} €) — vérifiez la répartition.")
            return redirect(url_for("immobilisations", annee=annee,
                ok=f"{cree} composant(s) créé(s) pour {total:.2f} €.{alerte}"))
        except Exception as exc:
            conn.rollback()
            return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
        finally:
            conn.close()


    @app.route("/immobilisations/composant/<int:composant_id>/duree",
               methods=["POST"])
    def composant_duree(composant_id):
        """
        Corrige la durée d'amortissement d'un composant.

        Ajouté après un blocage réel : un composant créé avec une durée sur un
        compte non amortissable (terrain) faisait échouer toute clôture, et
        RIEN dans l'interface ne permettait de le corriger — les composants
        étaient créables, jamais modifiables. Un logiciel qui laisse commettre
        une erreur doit laisser la défaire.
        """
        conn = _conn()
        annee = _annee_param(conn)
        try:
            c = conn.execute("SELECT libelle, compte_immo FROM composant "
                             "WHERE id=?", (composant_id,)).fetchone()
            if c is None:
                raise ValueError("Composant introuvable.")
            duree = amortissement.duree_valide(request.form.get("duree_annees", ""))
            amortissable = 1 if duree else 0
            cpt_amort = (plan_immo.compte_amortissement(c["compte_immo"])
                         if amortissable else None)
            if amortissable and not cpt_amort:
                raise ValueError(
                    f"Le compte {c['compte_immo']} ne s'amortit pas : seule la "
                    "durée 0 est acceptée pour ce composant.")
            conn.execute("UPDATE composant SET duree_annees=?, amortissable=?, "
                         "compte_amort=? WHERE id=?",
                         (duree, amortissable, cpt_amort, composant_id))
            conn.commit()
            msg = (f"Composant « {c['libelle']} » : durée portée à "
                   f"{duree} ans." if duree else
                   f"Composant « {c['libelle']} » : durée retirée, il n'est "
                   "plus amorti.")
            return redirect(url_for("immobilisations", annee=annee, ok=msg))
        except Exception as exc:
            return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
        finally:
            conn.close()


    @app.route("/immobilisations/composant/<int:composant_id>/supprimer",
               methods=["POST"])
    def composant_supprimer(composant_id):
        """Supprime un composant mal saisi et contre-passe son acquisition
        (règle et garde-fous dans `operations.supprimer_composant`)."""
        conn = _conn()
        annee = _annee_param(conn)
        try:
            r = operations.supprimer_composant(conn, composant_id)
            return redirect(url_for("immobilisations", annee=annee,
                                    ok=operations.message_suppression(r)))
        except Exception as exc:
            conn.rollback()
            return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
        finally:
            conn.close()


    @app.route("/immobilisations/reprendre-amortissements", methods=["POST"])
    def immo_reprendre_amortissements():
        """Passe le « à-nouveau » d'amortissement d'un bien déjà amorti à son
        entrée dans le logiciel. Constaté en usage réel : sans lui, le bilan et
        le tableau 2033-C divergent définitivement."""
        conn = _conn()
        annee = _annee_param(conn)
        try:
            r = operations.reprendre_amortissements_anterieurs(conn, annee)
            return redirect(url_for("immobilisations", annee=annee,
                                    ok=operations.message_reprise(r)))
        except Exception as exc:
            return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
        finally:
            conn.close()


    @app.route("/immobilisations/bien/<int:bien_id>/ceder", methods=["POST"])
    def bien_ceder(bien_id):
        conn = _conn()
        try:
            annee = _annee_param(conn)
            # Sentinelle None plutôt que -1 : un champ vide, un mot, « nan » ou
            # « inf » sont TOUS des saisies invalides, et les annoncer comme un
            # « prix négatif » envoyait l'utilisateur corriger un signe qu'il
            # n'avait pas tapé.
            prix = _form_float("prix_cession")
            if prix is None:
                raise ValueError("indiquez un prix de cession en euros "
                                 "(0 si la sortie se fait sans contrepartie).")
            r = cession.ceder_bien(
                conn, bien_id,
                date_cession=(request.form.get("date_cession") or "").strip(),
                prix_cession=prix)
            ok = (f"Cession de {r['bien']} enregistrée : dotation complémentaire "
                  f"{r['dotation_complementaire']:.2f} €, VNC sortie "
                  f"{r['vnc_sortie']:.2f} €, prix {r['prix_cession']:.2f} € "
                  f"({'plus' if r['pv_comptable'] >= 0 else 'moins'}-value comptable "
                  f"{abs(r['pv_comptable']):.2f} €, neutralisée fiscalement — "
                  "voir le Pense-bête pour les démarches).")
            return redirect(url_for("immobilisations", annee=annee, ok=ok))
        except Exception as exc:
            return redirect(url_for("immobilisations",
                                    annee=request.form.get("annee", type=int)
                                    or date.today().year,
                                    err=f"Cession refusée — {exc}"))
        finally:
            conn.close()
