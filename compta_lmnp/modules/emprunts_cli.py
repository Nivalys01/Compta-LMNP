# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Commandes « emprunt » de la ligne de commande.

Chaque geste de l'onglet Emprunts existe ici. `cli.py` les branche par
`ajouter_commandes(sub, ouvrir)` et annonce la base visée avant toute
commande, comme pour les autres. Un refus sort en code 1, message en clair.
"""
from __future__ import annotations

import datetime as _dt

import echeancier
import emprunts


def _executer(ouvrir, action):
    conn = ouvrir()
    try:
        return action(conn)
    except (ValueError, echeancier.LotAnnule) as exc:
        raise SystemExit(f"Refusé : {exc}") from None
    finally:
        conn.close()


def _periode(conn, a):
    annee = echeancier._aujourd_hui().year
    row = conn.execute("SELECT date_debut, date_fin FROM exercice WHERE annee=?",
                       (annee,)).fetchone()
    du, au = ((_dt.date.fromisoformat(row[0]), _dt.date.fromisoformat(row[1]))
              if row else (_dt.date(annee, 1, 1), _dt.date(annee, 12, 31)))
    return (_dt.date.fromisoformat(a.du) if a.du else du,
            _dt.date.fromisoformat(a.au) if a.au else au)


def _afficher_apercu(lignes):
    for x in lignes:
        e = x.echeance
        detail = x.motif or ", ".join(
            f"opération n° {o['id']}" + (" (annulée)" if o["annulee"] else "")
            for o in x.operations_liees)
        charges = sum(op["montant"] for op in e.operations)
        print(f"  {x.cle:<28} {e.libelle[:34]:<34} {charges:>9.2f}  "
              f"{echeancier.LIBELLES_STATUT[x.statut]:<13} {detail}")
        for d in x.doublons:
            print(f"      ⚠ doublon probable : {d['libelle'] or d['type']} du "
                  f"{d['date']}, {d['montant']:.2f} € (opération n° {d['id']}"
                  + (", importée" if d["source"] == "import" else "") + ")")
        for al in e.alertes:
            print(f"      ⚠ {al}")


def ajouter_commandes(sub, ouvrir) -> None:
    """`sub` : sous-analyseur de cli.py ; `ouvrir` : sa connexion."""
    s = sub.add_parser("emprunt", help="emprunts et tableau de remboursement")
    es = s.add_subparsers(required=True)

    def lister(a):
        def f(conn):
            liste = emprunts.lister(conn)
            if not liste:
                print("Aucun emprunt décrit.")
            for e in liste:
                print(f"n° {e['id']:<3} {e['preteur']} — {e['bien_libelle']} — "
                      f"{emprunts.euros_fr(e['capital'])} € à "
                      f"{e['taux_pourcent']} % nominal, {e['nb_echeances']} "
                      f"échéances {e['periodicite']}s — capital restant dû "
                      f"à ce jour {emprunts.euros_fr(e['crd_aujourd_hui'])} €"
                      + (f" — bien cédé le {e['date_cession']}"
                         if e["date_cession"] else ""))
        _executer(ouvrir, f)
    es.add_parser("lister").set_defaults(f=lister)

    def creer(a):
        def f(conn):
            eid = emprunts.creer(
                conn, bien_id=a.bien, preteur=a.preteur, reference=a.reference,
                capital=a.capital, taux=a.taux, nb_echeances=a.duree,
                periodicite=a.periodicite, date_deblocage=a.deblocage,
                date_premiere_echeance=a.premiere, assurance=a.assurance)
            v = emprunts.vue(conn, eid)
            print(f"Emprunt n° {eid} créé : {len(v['lignes'])} échéances, "
                  f"première de {emprunts.euros_fr(v['lignes'][0]['echeance'])}"
                  " € hors assurance. Comparez au tableau de la banque : "
                  "c'est lui qui fait foi.")
            print(emprunts.AIDE_TAUX)
            print(emprunts.AIDE_DEBLOCAGES)
        _executer(ouvrir, f)
    d = es.add_parser("creer")
    d.add_argument("--bien", type=int, required=True)
    d.add_argument("--preteur", required=True)
    d.add_argument("--reference")
    d.add_argument("--capital", required=True, help="ex. 150000 ou 150000,00")
    d.add_argument("--taux", required=True,
                   help="taux NOMINAL annuel en %% (ex. 3,5), pas le TAEG")
    d.add_argument("--duree", required=True, help="nombre d'échéances")
    d.add_argument("--periodicite", default="mensuelle",
                   choices=list(emprunts.PERIODICITES))
    d.add_argument("--deblocage", required=True, help="AAAA-MM-JJ")
    d.add_argument("--premiere", required=True,
                   help="date de la PREMIÈRE échéance, recopiée de l'offre")
    d.add_argument("--assurance", help="assurance par échéance (€)")
    d.set_defaults(f=creer)

    def tableau(a):
        def f(conn):
            v = emprunts.vue(conn, a.id)
            eur = emprunts.euros_fr
            print(f"Tableau de remboursement de l'emprunt n° {a.id} "
                  f"({v['emprunt']['preteur']}) :")
            print(f"  {'n°':>4} {'date':<10} {'capital':>11} {'intérêts':>10} "
                  f"{'assurance':>9} {'CRD après':>12}")
            for x in v["lignes"]:
                marque = "🔒" if x["verrouillee"] else "  "
                ecart = (f"  (calcul : {eur(x['interets_attendus'])})"
                         if x["interets_attendus"] is not None else "")
                print(f"{marque}{x['rang']:>4} {x['date'].strftime('%d/%m/%Y')} "
                      f"{eur(x['capital']):>11} {eur(x['interets']):>10} "
                      f"{eur(x['assurance']):>9} {eur(x['crd']):>12} "
                      f"{x['origine']}{ecart}")
            t = v["totaux"]
            print(f"  Totaux : capital {eur(t['capital'])} €, intérêts "
                  f"{eur(t['interets'])} €, assurance {eur(t['assurance'])} €.")
            if v["reliquat"]:
                print(f"⚠ {emprunts.alerte_reliquat(v['reliquat'])}")
        _executer(ouvrir, f)
    d = es.add_parser("tableau")
    d.add_argument("--id", type=int, required=True)
    d.set_defaults(f=tableau)

    def remplacer(a):
        def f(conn):
            r = emprunts.remplacer_ligne(
                conn, a.id, a.rang, date_echeance=a.date, capital=a.capital,
                interets=a.interets, assurance=a.assurance)
            print(f"Échéance n° {a.rang} remplacée"
                  + (f" ; {r['recalculees']} échéance(s) suivante(s) "
                     "recalculée(s)" if r["recalculees"] else "") + ".")
            if r["ecart_interets"] is not None:
                print("Note : intérêts différents de capital restant dû × taux "
                      f"({emprunts.euros_fr(r['ecart_interets'])} €) — "
                      "accepté, la banque fait foi.")
        _executer(ouvrir, f)
    d = es.add_parser("remplacer-ligne")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--rang", type=int, required=True)
    d.add_argument("--date", required=True)
    d.add_argument("--capital", required=True)
    d.add_argument("--interets", required=True)
    d.add_argument("--assurance", default="0")
    d.set_defaults(f=remplacer)

    def importer(a):
        def f(conn):
            with open(a.csv, "rb") as fh:
                r = emprunts.importer_csv(conn, a.id, fh.read())
            print(f"Tableau de la banque importé : {r['nb']} échéance(s) à "
                  f"partir de la n° {r['premier_rang']}.")
            if r["ecarts_interets"]:
                print(f"Note : {r['ecarts_interets']} échéance(s) aux intérêts "
                      "différents du calcul — acceptées, la banque fait foi.")
            if r["reliquat"]:
                print(f"⚠ {emprunts.alerte_reliquat(r['reliquat'])}")
        _executer(ouvrir, f)
    d = es.add_parser("importer")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--csv", required=True)
    d.set_defaults(f=importer)

    def exporter(a):
        def f(conn):
            texte = emprunts.exporter_csv(conn, a.id)
            with open(a.out, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write(texte)
            print(f"Tableau exporté : {a.out}")
        _executer(ouvrir, f)
    d = es.add_parser("exporter")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--out", required=True)
    d.set_defaults(f=exporter)

    def apercu(a):
        def f(conn):
            du, au = _periode(conn, a)
            print(f"Échéances du {du} au {au} :")
            _afficher_apercu(emprunts.apercu(conn, du, au))
            print(emprunts.RAPPEL_CHARGES)
        _executer(ouvrir, f)

    def generer(a):
        def f(conn):
            du, au = _periode(conn, a)
            lignes = emprunts.apercu(conn, du, au)
            exclues = set(a.exclure or ())
            retenues = {x.cle for x in lignes
                        if x.cochee_par_defaut and x.cle not in exclues}
            retenues |= set(a.inclure or ())
            ecarter = set(a.ecarter or ())
            print(f"Échéances du {du} au {au} :")
            _afficher_apercu(lignes)
            print(f"\n{len(retenues)} échéance(s) retenue(s)"
                  + (f", {len(ecarter)} à écarter" if ecarter else "")
                  + ". Les doublons probables et les échéances signalées ne "
                    "sont retenus que par --inclure.")
            if not retenues and not ecarter:
                return
            if not a.oui:
                rep = input("Passer ces échéances en écriture ? [o/N] ")
                if rep.strip().lower() not in ("o", "oui"):
                    print("Abandon : rien n'a été généré.")
                    return
            print(emprunts.message_generation(
                emprunts.generer(conn, du, au, retenues, ecarter=ecarter)))
        _executer(ouvrir, f)

    for nom, fn in (("apercu", apercu), ("generer", generer)):
        d = es.add_parser(nom)
        d.add_argument("--du", help="AAAA-MM-JJ (défaut : exercice de l'année)")
        d.add_argument("--au", help="AAAA-MM-JJ")
        if nom == "generer":
            d.add_argument("--exclure", action="append", metavar="CLE")
            d.add_argument("--inclure", action="append", metavar="CLE",
                           help="retenir malgré un doublon ou une alerte")
            d.add_argument("--ecarter", action="append", metavar="CLE",
                           help="déjà passée autrement : ne plus proposer")
            d.add_argument("--oui", action="store_true",
                           help="sans confirmation")
        d.set_defaults(f=fn)

    def retablir(a):
        def f(conn):
            echeancier.retablir(conn, a.cle)
            print("Échéance rétablie : de nouveau proposée, et sa ligne du "
                  "tableau redevient modifiable.")
        _executer(ouvrir, f)
    d = es.add_parser("retablir")
    d.add_argument("--cle", required=True)
    d.set_defaults(f=retablir)

    def supprimer(a):
        if not a.oui:
            rep = input(f"Supprimer l'emprunt n° {a.id} et son tableau ? [o/N] ")
            if rep.strip().lower() not in ("o", "oui"):
                print("Abandon : rien n'a été supprimé.")
                return

        def f(conn):
            emprunts.supprimer(conn, a.id)
            print(f"Emprunt n° {a.id} supprimé.")
        _executer(ouvrir, f)
    d = es.add_parser("supprimer")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--oui", action="store_true", help="sans confirmation")
    d.set_defaults(f=supprimer)
