# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
CLI — interface de saisie LMNP.

Exemples :
    python cli.py init
    python cli.py saisir --type loyer --montant 795 --periode 2026-03 --date 2026-03-05
    python cli.py importer --csv releve.csv            # propose (ne saisit pas)
    python cli.py importer --csv releve.csv --valider  # saisit les propositions
    python cli.py controler --annee 2026
    python cli.py exporter --annee 2026 --out FEC2026.txt
    python cli.py gabarits
    python cli.py depot ajouter --annee 2026 --type liasse --nature initiale --date 2027-05-12 --reference ABC123
    python cli.py depot lister --annee 2026
    python cli.py depot supprimer --id 3
    python cli.py recurrent ajouter --type assurance --bien 1 --montant 18.50 --periodicite mensuelle --jour 31 --debut 2026-01-31
    python cli.py recurrent apercu --du 2026-01-01 --au 2026-12-31
    python cli.py recurrent generer --du 2026-01-01 --au 2026-12-31
    python cli.py emprunt creer --bien 1 --preteur "Banque" --capital 150000 --taux 3,5 --duree 240 --deblocage 2026-01-10 --premiere 2026-02-05
    python cli.py emprunt importer --id 1 --csv tableau_banque.csv
    python cli.py emprunt generer --du 2026-01-01 --au 2026-12-31
"""
from __future__ import annotations
import argparse
import os
import sqlite3

import sys

# ── Amorçage du chemin d'import ───────────────────────────────────────────
#    Les modules métier vivent dans modules/ : sans ces lignes, « import
#    fiscal » échoue. Le paquet n'est pas installé par pip — c'est le prix
#    d'une distribution par simple décompression, et le lanceur ne peut pas
#    le faire à notre place. À poser AVANT le premier import métier.
_MODULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
if _MODULES not in sys.path:
    sys.path.insert(0, _MODULES)

import init_db
import operations
import controles
import depots
import echeancier
import emprunts_cli
import export_fec
import import_bancaire
import fiscal
from gabarits import GABARITS
HERE = os.path.dirname(os.path.abspath(__file__))
# Base visée par la ligne de commande. Elle était codée en dur sur le
# dossier principal, alors que l'interface web résout le dossier courant
# par son registre : quelqu'un travaillant depuis des semaines dans un
# dossier secondaire voyait ses commandes agir sur le dossier principal —
# une clôture dans un dossier qu'il ne regardait plus, et celui qu'il
# voulait clore resté ouvert. Le chemin n'apparaissait nulle part.
DB = os.environ.get("COMPTA_DB") or os.path.join(HERE, "compta.db")
FEC_REF = os.path.join(HERE, "reference/FEC_REFERENCE_2025.txt")


def _conn() -> sqlite3.Connection:
    if not os.path.exists(DB):
        raise SystemExit(
            f"Aucune base à cet emplacement : {DB}\n"
            "Créez-la depuis la page « Dossiers » du logiciel, ou visez un "
            "autre dossier avec --dossier / COMPTA_DB.")
    c = sqlite3.connect(DB)
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _annoncer_base() -> None:
    """Dit TOUJOURS sur quelle base on agit. Le défaut le plus insidieux de
    cette interface était de n'en rien dire."""
    print(f"Dossier : {DB}")


def _resoudre_dossier(slug: str | None) -> None:
    """Vise un dossier du registre plutôt que le dossier principal."""
    global DB
    if not slug:
        return
    try:
        import dossiers
        chemin = dossiers.chemin_db(HERE, slug)
    except Exception as exc:                     # noqa: BLE001
        raise SystemExit(f"Dossier « {slug} » introuvable : {exc}") from exc
    if not chemin or not os.path.exists(chemin):
        raise SystemExit(f"Dossier « {slug} » introuvable dans le registre.")
    DB = chemin


def cmd_init(a):
    init_db.init(DB, a.mode, fec_path=FEC_REF, annee_cible=a.annee).close()
    if a.mode == "demo":
        print(f"Base initialisée : {DB} (mode demo, à-nouveaux {a.annee} repris).")
    else:
        print(f"Base initialisée : {DB} (mode blanc, dossier vierge, exercice {a.annee}).")


def cmd_gabarits(a):
    print("Types d'opération disponibles :")
    for t, g in sorted(GABARITS.items()):
        extra = "  [seuil immo]" if g.get("seuil_immo") else ("  [à requalifier]" if g.get("requalifier") else "")
        print(f"  {t:<18} -> {g['compte']} {g['libelle']} ({g['periodicite']}){extra}")


def cmd_saisir(a):
    conn = _conn()
    r = operations.saisir(conn, type=a.type, montant=a.montant, date_operation=a.date,
                          periode=a.periode, tiers=a.tiers or "", libelle=a.libelle)
    conn.close()
    print(f"Opération {r['operation_id']} saisie -> écriture BQ n°{r['ecriture_num']}.")


def cmd_importer(a):
    conn = _conn()
    rejets = import_bancaire.analyser(a.csv, conn)["rejets"]
    props = import_bancaire.importer(conn, a.csv, valider=a.valider)
    conn.close()
    if rejets:
        # Rendre compte AVANT la liste : une ligne non lue est une charge
        # non déduite ou une recette non déclarée, pas un détail.
        print(f"ATTENTION — {len(rejets)} ligne(s) non lue(s) :")
        for r in rejets:
            print(f"  ligne {r['ligne']:>4} : {r['raison']}  |  {r['contenu']}")
        print()
    print(f"{len(props)} ligne(s) {'importée(s)' if a.valider else 'proposée(s)'} :")
    for p in props:
        per = p["periode"] or "-"
        print(f"  {p['date_operation']}  {p['montant']:>9.2f}  {p['type']:<16} {per:<8} {p['libelle']}")
    if not a.valider:
        print("\n(Relancer avec --valider pour saisir ces opérations.)")


def cmd_controler(a):
    conn = _conn()
    print(controles.rapport(conn, a.annee))
    # Hors du moteur (voir depots) : affichés à la suite, pas dans le bilan.
    for ano in depots.controler(conn, a.annee):
        print(f"  [{ano.niveau:<13}] {ano.code:<13} {ano.message}")
    conn.close()


def cmd_depot_ajouter(a):
    conn = _conn()
    try:
        n = depots.enregistrer(conn, annee=a.annee, type=a.type,
                               nature=a.nature, date_depot=a.date,
                               reference=a.reference, note=a.note)
    except ValueError as exc:
        raise SystemExit(f"Dépôt refusé : {exc}") from None
    finally:
        conn.close()
    print(f"Dépôt n° {n} enregistré.")


def cmd_depot_lister(a):
    conn = _conn()
    try:
        for t, liste in depots.lister(conn, a.annee).items():
            print(f"{depots.TYPES[t]} — exercice {a.annee}")
            if not liste:
                print("  aucun dépôt enregistré")
            for d in liste:
                print(f"  n° {d['id']:<4} {d['nature']:<13} {d['date_depot']}  "
                      f"{d['reference'] or '—'}  {d['note'] or ''}".rstrip())
        for ano in depots.controler(conn, a.annee):
            print(f"[{ano.niveau}] {ano.code} {ano.message}")
    finally:
        conn.close()


def cmd_depot_supprimer(a):
    if not a.oui:
        rep = input(f"Supprimer le dépôt n° {a.id} ? La ligne sera effacée. "
                    "[o/N] ")
        if rep.strip().lower() not in ("o", "oui"):
            print("Abandon : rien n'a été supprimé.")
            return
    conn = _conn()
    try:
        print(depots.message_suppression(depots.supprimer(conn, a.id)))
    except ValueError as exc:
        raise SystemExit(f"Suppression refusée : {exc}") from None
    finally:
        conn.close()


def _recurrent(a, action):
    """Exécute une action sur les modèles ; un refus sort en code 1."""
    import recurrentes
    conn = _conn()
    try:
        return action(conn, recurrentes)
    except (ValueError, echeancier.LotAnnule) as exc:
        raise SystemExit(f"Refusé : {exc}") from None
    finally:
        conn.close()


def _champs_modele(a) -> dict:
    noms = {"type": "type", "bien": "bien_id", "montant": "montant",
            "periodicite": "periodicite", "jour": "jour",
            "debut": "date_debut", "fin": "date_fin", "libelle": "libelle",
            "tiers": "tiers"}
    return {cle: getattr(a, arg) for arg, cle in noms.items()
            if getattr(a, arg, None) is not None}


def _aide_gabarit(recurrentes, type_):
    if type_ in recurrentes.AIDES:
        print(f"Note : {recurrentes.AIDES[type_]}")


def cmd_recurrent_lister(a):
    def f(conn, R):
        modeles = R.lister(conn)
        if not modeles:
            print("Aucun modèle récurrent.")
        for m in modeles:
            print(f"n° {m['id']:<3} {'actif   ' if m['actif'] else 'suspendu'} "
                  f"{m['libelle'] or m['gabarit_libelle']} — {m['bien_libelle']} "
                  f"— {m['montant']:.2f} € {m['periodicite']}, "
                  f"{m['jour_libelle']}, du {m['date_debut']}"
                  + (f" au {m['date_fin']}" if m["date_fin"] else ""))
    _recurrent(a, f)


def cmd_recurrent_ajouter(a):
    def f(conn, R):
        n = R.creer(conn, **_champs_modele(a))
        print(f"Modèle n° {n} créé.")
        _aide_gabarit(R, a.type)
    _recurrent(a, f)


def cmd_recurrent_depuis_operation(a):
    def f(conn, R):
        n = R.depuis_operation(conn, a.id, periodicite=a.periodicite)
        m = R.modele(conn, n)
        print(f"Modèle n° {n} créé depuis l'opération {a.id} "
              f"({a.periodicite}, le {m['jour']}, à partir du "
              f"{m['date_debut']}). Vérifiez-le avec « recurrent lister ».")
        _aide_gabarit(R, m["type"])
    _recurrent(a, f)


def cmd_recurrent_modifier(a):
    def f(conn, R):
        R.modifier(conn, a.id, **_champs_modele(a))
        print(f"Modèle n° {a.id} modifié. Les opérations déjà générées ne "
              "changent pas.")
    _recurrent(a, f)


def cmd_recurrent_etat(a):
    def f(conn, R):
        R.activer(conn, a.id, a.actif)
        print(f"Modèle n° {a.id} {'repris' if a.actif else 'suspendu'}.")
    _recurrent(a, f)


def cmd_recurrent_supprimer(a):
    if not a.oui:
        rep = input(f"Supprimer le modèle n° {a.id} ? Les opérations déjà "
                    "générées sont conservées ; un modèle recréé à l'identique "
                    "reproposera les échéances passées. [o/N] ")
        if rep.strip().lower() not in ("o", "oui"):
            print("Abandon : rien n'a été supprimé.")
            return

    def f(conn, R):
        r = R.supprimer(conn, a.id)
        print(f"Modèle n° {a.id} supprimé ; {r['operations_conservees']} "
              "opération(s) déjà générée(s) conservée(s).")
    _recurrent(a, f)


def _periode(conn, R, a):
    import datetime as _dt
    annee = echeancier._aujourd_hui().year
    du, au = R.periode_par_defaut(conn, annee)
    return (_dt.date.fromisoformat(a.du) if a.du else du,
            _dt.date.fromisoformat(a.au) if a.au else au)


def _afficher_apercu(lignes):
    for x in lignes:
        e = x.echeance
        detail = x.motif or ", ".join(
            f"opération n° {o['id']}" + (" (annulée)" if o["annulee"] else "")
            for o in x.operations_liees)
        print(f"  {x.cle:<32} {e.libelle[:30]:<30} "
              f"{sum(op['montant'] for op in e.operations):>9.2f}  "
              f"{echeancier.LIBELLES_STATUT[x.statut]:<13} {detail}")
        for d in x.doublons:
            print(f"      ⚠ doublon probable : {d['libelle'] or d['type']} du "
                  f"{d['date']} (opération n° {d['id']}"
                  + (", importée" if d["source"] == "import" else "") + ")")


def cmd_recurrent_apercu(a):
    def f(conn, R):
        du, au = _periode(conn, R, a)
        print(f"Échéances du {du} au {au} :")
        _afficher_apercu(R.apercu(conn, du, au))
    _recurrent(a, f)


def cmd_recurrent_generer(a):
    def f(conn, R):
        du, au = _periode(conn, R, a)
        lignes = R.apercu(conn, du, au)
        exclues = set(a.exclure or ())
        retenues = {x.cle for x in lignes
                    if x.cochee_par_defaut and x.cle not in exclues}
        retenues |= {c for c in (a.inclure or ())}
        ecarter = set(a.ecarter or ())
        print(f"Échéances du {du} au {au} :")
        _afficher_apercu(lignes)
        print(f"\n{len(retenues)} échéance(s) retenue(s)"
              + (f", {len(ecarter)} à écarter" if ecarter else "")
              + ". Les doublons probables ne sont retenus que par --inclure.")
        if not retenues and not ecarter:
            return
        if not a.oui:
            rep = input("Générer ces opérations ? [o/N] ")
            if rep.strip().lower() not in ("o", "oui"):
                print("Abandon : rien n'a été généré.")
                return
        print(R.message_generation(
            R.generer(conn, du, au, retenues, ecarter=ecarter)))
    _recurrent(a, f)


def cmd_recurrent_retablir(a):
    def f(conn, R):
        echeancier.retablir(conn, a.cle)
        print("Échéance rétablie.")
    _recurrent(a, f)


def cmd_cloturer(a):
    conn = _conn()
    # La clôture web prend une sauvegarde et archive le FEC ; la version en
    # ligne de commande ne faisait ni l'un ni l'autre. Même opération,
    # même irréversibilité, même piste d'audit à conserver.
    try:
        import perennite
        sv = perennite.sauvegarder(DB, motif="avant-cloture")
        if sv:
            print(f"Sauvegarde : {sv['chemin'] if isinstance(sv, dict) else sv}")
    except Exception as exc:                     # noqa: BLE001
        raise SystemExit(
            f"Clôture refusée : la sauvegarde préalable a échoué ({exc}).") from exc
    # Contrôles d'abord : pas de clôture si anomalie bloquante.
    anos = controles.controler(conn, a.annee)
    bloq = controles.bloquants(anos)
    if bloq and not a.forcer:
        print(controles.rapport(conn, a.annee))
        print("\n⛔ Clôture refusée (anomalies bloquantes). Corrige-les ou utilise --forcer.")
        conn.close()
        # Le CODE DE RETOUR est le verdict pour tout ce qui appelle cette
        # commande autrement qu'en la lisant : script de sauvegarde, tâche
        # planifiée, chaîne d'intégration. Il valait 0 sur un refus, et un
        # appelant pouvait donc enchaîner comme si la clôture avait eu
        # lieu. Le texte affiché était pourtant sans ambiguïté : c'est le
        # contrat de commande qui manquait.
        raise SystemExit(1)
    res = fiscal.cloturer(conn, a.annee, autres_retraitements=a.retraitements,
                          forcer=a.forcer)
    # Archivage du FEC : la version web le fait, celle-ci ne le faisait PAS,
    # alors que le commentaire ci-dessus affirmait le contraire. Une clôture
    # en ligne de commande ne laissait donc aucune trace dans archives/ ni
    # aucune ligne dans manifeste.csv : la piste d'audit — FEC figé et son
    # empreinte SHA-256 — manquait pour tout exercice clos hors du web.
    #
    # Et comme côté web, l'archivage vient APRÈS une clôture déjà committée :
    # son échec est un avertissement, pas un échec de clôture.
    try:
        arch = perennite.archiver_fec(conn, a.annee, DB)
        print(f"FEC archivé : {arch['chemin']}")
        print(f"  empreinte SHA-256 : {arch['sha256'][:16]}… "
              f"(consignée dans {os.path.basename(arch['manifeste'])})")
    except Exception as exc:                         # noqa: BLE001
        print(f"\nATTENTION : l'exercice {a.annee} EST clôturé, mais le FEC "
              f"n'a pas pu être archivé ({exc}).")
        print("  La piste d'audit manque : exportez le FEC à la main avec "
              "« exporter-fec ».")
    conn.close()
    ag, s, d = res["agregats"], res["suivi_39c"], res["deficits"]
    print(f"Clôture {a.annee} :")
    print(f"  Produits {ag['produits']:.2f} | Charges {ag['charges_hors_daa']:.2f} | "
          f"Dotation {ag['dotation']:.2f}")
    print(f"  Résultat comptable : {ag['resultat_comptable']:.2f}")
    print(f"  Report 39C : +{s['report_annee']:.2f} / -{s['utilisation_annee']:.2f} "
          f"-> stock {s['stock_cloture']:.2f}")
    print(f"  Résultat fiscal    : {res['resultat_fiscal']:.2f}")
    print(f"  Déficits LMNP : stock {d['stock_deficits']:.2f}"
          + (f" (déficit créé {d['deficit_cree']:.2f})" if d['deficit_cree'] else "")
          + (f" (imputé {d['impute_sur_benefice']:.2f})" if d['impute_sur_benefice'] else ""))


def cmd_exporter(a):
    conn = _conn()
    chemin = export_fec.exporter(conn, a.annee, a.out)
    conn.close()
    print(f"FEC exporté : {chemin}")


def main():
    p = argparse.ArgumentParser(prog="cli.py")
    # Option COMMUNE : viser un dossier du registre. Sans elle, toutes les
    # commandes agissaient sur le dossier principal, quel que soit celui
    # dans lequel l'utilisateur travaillait par l'interface.
    p.add_argument("--dossier", metavar="SLUG",
                   help="dossier du registre à viser (défaut : dossier "
                        "principal). Voir la page « Dossiers ».")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("init")
    s.add_argument("--mode", choices=["blanc", "demo"], default="blanc")
    s.add_argument("--annee", type=int, default=None)
    s.set_defaults(f=cmd_init)
    s = sub.add_parser("gabarits")
    s.set_defaults(f=cmd_gabarits)

    s = sub.add_parser("saisir")
    s.add_argument("--type", required=True)
    s.add_argument("--montant", type=float, required=True)
    s.add_argument("--date", required=True)
    s.add_argument("--periode")
    s.add_argument("--tiers")
    s.add_argument("--libelle")
    s.set_defaults(f=cmd_saisir)

    s = sub.add_parser("importer")
    s.add_argument("--csv", required=True)
    s.add_argument("--valider", action="store_true")
    s.set_defaults(f=cmd_importer)

    s = sub.add_parser("controler")
    s.add_argument("--annee", type=int, default=2026)
    s.set_defaults(f=cmd_controler)

    s = sub.add_parser("cloturer")
    s.add_argument("--annee", type=int, default=2026)
    s.add_argument("--retraitements", type=float, default=0.0,
                   help="autres retraitements fiscaux. NE PAS y mettre le fonds de "
                        "travaux ALUR : il est déjà réintégré automatiquement, "
                        "et les deux montants s'additionneraient.")
    s.add_argument("--forcer", action="store_true", help="clôturer malgré les anomalies bloquantes")
    s.set_defaults(f=cmd_cloturer)

    s = sub.add_parser("depot", help="suivi des dépôts de déclaration")
    ds = s.add_subparsers(required=True)
    d = ds.add_parser("ajouter")
    d.add_argument("--annee", type=int, required=True)
    d.add_argument("--type", required=True,
                   help="liasse (2031/2033) ou 2042 (2042-C-PRO)")
    d.add_argument("--nature", choices=list(depots.NATURES), required=True)
    d.add_argument("--date", required=True, help="date de dépôt AAAA-MM-JJ")
    d.add_argument("--reference", help="référence de l'accusé de réception")
    d.add_argument("--note")
    d.set_defaults(f=cmd_depot_ajouter)
    d = ds.add_parser("lister")
    d.add_argument("--annee", type=int, required=True)
    d.set_defaults(f=cmd_depot_lister)
    d = ds.add_parser("supprimer")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--oui", action="store_true", help="sans confirmation")
    d.set_defaults(f=cmd_depot_supprimer)

    s = sub.add_parser("recurrent", help="charges récurrentes")
    rs = s.add_subparsers(required=True)

    def _args_modele(d, requis):
        d.add_argument("--type", required=requis, help="gabarit de charge admis")
        d.add_argument("--bien", type=int, required=requis)
        d.add_argument("--montant", type=float, required=requis)
        d.add_argument("--periodicite", required=requis,
                       choices=["mensuelle", "trimestrielle", "semestrielle",
                                "annuelle"])
        d.add_argument("--jour", required=requis,
                       help="1 à 31, ou « dernier » (dernier jour du mois)")
        d.add_argument("--debut", required=requis, help="AAAA-MM-JJ")
        d.add_argument("--fin", help="AAAA-MM-JJ")
        d.add_argument("--libelle")
        d.add_argument("--tiers")

    d = rs.add_parser("lister")
    d.set_defaults(f=cmd_recurrent_lister)
    d = rs.add_parser("ajouter")
    _args_modele(d, True)
    d.set_defaults(f=cmd_recurrent_ajouter)
    d = rs.add_parser("depuis-operation")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--periodicite", default="mensuelle",
                   choices=["mensuelle", "trimestrielle", "semestrielle",
                            "annuelle"])
    d.set_defaults(f=cmd_recurrent_depuis_operation)
    d = rs.add_parser("modifier")
    d.add_argument("--id", type=int, required=True)
    _args_modele(d, False)
    d.set_defaults(f=cmd_recurrent_modifier)
    for nom, actif in (("suspendre", False), ("reprendre", True)):
        d = rs.add_parser(nom)
        d.add_argument("--id", type=int, required=True)
        d.set_defaults(f=cmd_recurrent_etat, actif=actif)
    d = rs.add_parser("supprimer")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--oui", action="store_true", help="sans confirmation")
    d.set_defaults(f=cmd_recurrent_supprimer)
    for nom, fn in (("apercu", cmd_recurrent_apercu),
                    ("generer", cmd_recurrent_generer)):
        d = rs.add_parser(nom)
        d.add_argument("--du", help="AAAA-MM-JJ (défaut : exercice de l'année)")
        d.add_argument("--au", help="AAAA-MM-JJ")
        if nom == "generer":
            d.add_argument("--exclure", action="append", metavar="CLE",
                           help="échéance à ne pas générer cette fois")
            d.add_argument("--inclure", action="append", metavar="CLE",
                           help="retenir malgré un doublon probable")
            d.add_argument("--ecarter", action="append", metavar="CLE",
                           help="ne plus proposer cette échéance")
            d.add_argument("--oui", action="store_true",
                           help="sans confirmation")
        d.set_defaults(f=fn)
    d = rs.add_parser("retablir")
    d.add_argument("--cle", required=True)
    d.set_defaults(f=cmd_recurrent_retablir)

    emprunts_cli.ajouter_commandes(sub, _conn)

    s = sub.add_parser("exporter")
    s.add_argument("--annee", type=int, default=2026)
    s.add_argument("--out", default="FEC.txt")
    s.set_defaults(f=cmd_exporter)

    args = p.parse_args()
    _resoudre_dossier(getattr(args, "dossier", None))
    _annoncer_base()
    args.f(args)


if __name__ == "__main__":
    main()
