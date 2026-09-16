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
    conn.close()


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
