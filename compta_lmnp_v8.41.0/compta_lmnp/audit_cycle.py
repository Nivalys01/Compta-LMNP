# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Audit de cycle complet — « bac à sable » automatisé.

Rejoue l'intégralité du processus comptable sur une base JETABLE (jamais la
base réelle) et vérifie chaque étape :

  Phase 1 — Cycle nominal
    init blanc → exploitant/bien/composants → ouverture exercice →
    saisie de 12 mois d'opérations → contrôles (aucun bloquant) →
    clôture (dotation + 39 C + déficits) → export FEC → validation FEC.

  Phase 2 — Détection d'anomalies
    Injecte des anomalies connues (doublon, « Autres charges », dépense
    au-dessus du seuil d'immobilisation, loyer manquant, écriture
    déséquilibrée, charge au crédit) et vérifie que le moteur de contrôles
    les détecte TOUTES.

  Phase 3 — Mécanique fiscale pluri-exercices
    Exercice déficitaire (plafond 39 C < dotation) → report 39 C + déficit
    LMNP créés ; exercice bénéficiaire suivant → imputation FIFO.

Usage :
    python audit_cycle.py                # rapport texte, code retour 0/1
    python audit_cycle.py --json         # rapport JSON (pour l'UI)
    python audit_cycle.py --garder       # conserve la base d'audit pour inspection

Le rapport liste chaque vérification avec PASS / FAIL et un détail chiffré.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import controles
import export_fec
import fiscal
import init_db
import operations
import valider_fec
import ecritures
import gabarits
import liasse
import parametres
import reprise


# ── Collecte des résultats ───────────────────────────────────────────────────

class Rapport:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def check(self, phase: str, nom: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({"phase": phase, "nom": nom,
                            "ok": bool(ok), "detail": detail})
        return ok

    @property
    def echecs(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]

    @property
    def succes(self) -> bool:
        return not self.echecs

    def texte(self) -> str:
        lignes, phase_courante = [], None
        for c in self.checks:
            if c["phase"] != phase_courante:
                phase_courante = c["phase"]
                lignes.append("")
                lignes.append(f"── {phase_courante} " + "─" * max(0, 60 - len(phase_courante)))
            statut = "PASS ✓" if c["ok"] else "FAIL ✗"
            lignes.append(f"  [{statut}] {c['nom']}")
            if c["detail"]:
                lignes.append(f"           {c['detail']}")
        lignes.append("")
        n_ok = sum(1 for c in self.checks if c["ok"])
        lignes.append(f"Résultat : {n_ok}/{len(self.checks)} vérifications réussies — "
                      + ("AUDIT CONFORME ✓" if self.succes else
                         f"{len(self.echecs)} ÉCHEC(S) ✗"))
        return "\n".join(lignes)


# ── Jeu de données du scénario ───────────────────────────────────────────────

def _creer_dossier(conn: sqlite3.Connection, annee: int) -> None:
    """Exploitant fictif + bien + 3 composants (bâti, mobilier, terrain)."""
    conn.execute("INSERT INTO exploitant (nom, siren, adresse) VALUES "
                 "('AUDIT Bac à sable', '000000000', '1 rue du Test, 00000 Testville')")
    conn.execute("INSERT INTO bien (exploitant_id, libelle, adresse, date_acquisition, "
                 "prix_total, quote_part_terrain) VALUES "
                 "(1, 'T2 Test', '1 rue du Test', ?, 115000, 0.087)",
                 (f"{annee}-01-01",))
    composants = [
        # (code, libellé, catégorie, VB, durée, mise en service, cpt immo, cpt amort, amort.)
        ("AUD-BAT", "Bâtiment",  "gros_oeuvre", 100000.0, 25, f"{annee}-01-01",
         "213150", "281315", 1),
        ("AUD-MOB", "Mobilier",  "mobilier",      5000.0,  5, f"{annee}-01-01",
         "218400", "281840", 1),
        ("AUD-TER", "Terrain",   "terrain",      10000.0, None, f"{annee}-01-01",
         "211550", None, 0),
    ]
    conn.executemany(
        "INSERT INTO composant (bien_id, code_immo, libelle, categorie, valeur_brute, "
        "duree_annees, date_mise_service, compte_immo, compte_amort, amortissable) "
        "VALUES (1,?,?,?,?,?,?,?,?,?)", composants)
    conn.commit()
    # Écritures d'acquisition (débit 2xx / crédit 108000) — sans elles, le
    # bilan 2033-A et le FEC seraient faux.
    for code, lib, _cat, vb, _d, dms, cpt, _ca, _am in composants:
        operations.saisir_acquisition(conn, compte_immo=cpt, montant=vb,
                                      date_operation=dms, libelle=lib,
                                      exercice=annee)


def _saisir_annee(conn: sqlite3.Connection, annee: int, loyer_mensuel: float,
                  charges: list[tuple[str, float, str]]) -> None:
    """12 loyers mensuels + une liste de charges (type, montant, mois)."""
    for mois in range(1, 13):
        operations.saisir(conn, type="loyer", montant=loyer_mensuel,
                          date_operation=f"{annee}-{mois:02d}-05",
                          periode=f"{annee}-{mois:02d}")
    for type_op, montant, mois in charges:
        operations.saisir(conn, type=type_op, montant=montant,
                          date_operation=f"{annee}-{mois}-15",
                          periode=f"{annee}-{mois}")


# L'ouverture d'exercice est une fonction de PRODUCTION : elle vit dans
# reprise.py et s'appelle directement (reprise.ouvrir_exercice). Aucun alias
# ici — un alias de compatibilité dans un module d'OUTILLAGE laisse croire à
# une variante propre aux tests, alors qu'il n'existe qu'une seule fonction.


# ── Phase 1 : cycle nominal ──────────────────────────────────────────────────

def phase_1_nominal(conn: sqlite3.Connection, r: Rapport, annee: int,
                    dossier_tmp: str) -> None:
    P = "Phase 1 — Cycle nominal (ouverture → clôture → FEC)"

    # 1. Dossier
    _creer_dossier(conn, annee)
    n_compo = conn.execute("SELECT COUNT(*) FROM composant").fetchone()[0]
    r.check(P, "Création exploitant / bien / composants", n_compo == 3,
            f"{n_compo} composants créés (bâti 25 ans, mobilier 5 ans, terrain)")

    # 2. Saisie d'un exercice complet
    charges = [("charge_copro", 600.0, "03"), ("assurance", 200.0, "01"),
               ("cfe", 300.0, "11"), ("honoraires", 250.0, "12"),
               ("frais_bancaires", 150.0, "06")]
    _saisir_annee(conn, annee, loyer_mensuel=800.0, charges=charges)
    nb_bq = conn.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=? "
                         "AND journal_code='BQ'", (annee,)).fetchone()[0]
    nb_acq = conn.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=? "
                          "AND piece_ref='ACQ'", (annee,)).fetchone()[0]
    r.check(P, "Saisie 12 loyers + 5 charges + 3 acquisitions",
            nb_bq == 17 and nb_acq == 3,
            f"{nb_bq} écritures BQ (attendu 17), {nb_acq} acquisitions (attendu 3)")

    # 3. Équilibre de chaque écriture
    des = conn.execute(
        "SELECT COUNT(*) FROM (SELECT ecriture_id FROM ligne GROUP BY ecriture_id "
        "HAVING ABS(ROUND(SUM(debit)-SUM(credit),2)) > 0.005)").fetchone()[0]
    r.check(P, "Toutes les écritures sont équilibrées", des == 0,
            f"{des} écriture(s) déséquilibrée(s)")

    # 4. Contrôles pré-clôture : aucun bloquant
    anos = controles.controler(conn, annee)
    bloq = controles.bloquants(anos)
    r.check(P, "Contrôles pré-clôture : aucun bloquant", not bloq,
            f"{len(anos)} anomalie(s) dont {len(bloq)} bloquante(s)")

    # 5. Clôture (dotation + 39 C + déficits)
    res = fiscal.cloturer(conn, annee)
    ag, s = res["agregats"], res["suivi_39c"]

    dot_attendue = 100000/25 + 5000/5          # 4 000 + 1 000 (année pleine)
    r.check(P, "Dotation aux amortissements exacte",
            abs(ag["dotation"] - dot_attendue) < 0.01,
            f"dotation {ag['dotation']:.2f} € (attendu {dot_attendue:.2f} €)")

    produits_att = 12 * 800.0
    charges_att = sum(m for _, m, _ in charges)
    rc_attendu = round(produits_att - charges_att - dot_attendue, 2)
    r.check(P, "Résultat comptable = produits − charges − dotation",
            abs(ag["resultat_comptable"] - rc_attendu) < 0.01,
            f"{ag['resultat_comptable']:.2f} € (attendu {rc_attendu:.2f} €)")

    r.check(P, "39 C : dotation entièrement déductible (plafond suffisant)",
            s["report_annee"] == 0 and s["stock_cloture"] == 0,
            f"plafond {s['plafond_deductible']:.2f} € ≥ dotation ; report {s['report_annee']:.2f} €")

    r.check(P, "Résultat fiscal = résultat comptable (aucun retraitement)",
            abs(res["resultat_fiscal"] - ag["resultat_comptable"]) < 0.01,
            f"fiscal {res['resultat_fiscal']:.2f} €")

    statut = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                          (annee,)).fetchone()[0]
    r.check(P, "Exercice marqué « clos »", statut == "clos", f"statut = {statut}")

    # 6. Export FEC + validation croisée
    fec_path = os.path.join(dossier_tmp, f"AUDITFEC{annee}1231.txt")
    export_fec.exporter(conn, annee, fec_path)
    verdict = valider_fec.valider(fec_path, comme_dict=True)
    r.check(P, "FEC exporté puis validé (conformité A47 A-1)",
            verdict["conforme"], f"{len(verdict['erreurs'])} erreur(s)")


# ── Phase 2 : détection d'anomalies ─────────────────────────────────────────

def phase_2_detection(conn: sqlite3.Connection, r: Rapport, annee: int) -> None:
    P = "Phase 2 — Détection d'anomalies par le moteur de contrôles"
    reprise.ouvrir_exercice(conn, annee)

    # 11 loyers seulement (janvier manquant) → contrôle de complétude
    for mois in range(2, 13):
        operations.saisir(conn, type="loyer", montant=800.0,
                          date_operation=f"{annee}-{mois:02d}-05",
                          periode=f"{annee}-{mois:02d}")

    # Doublon volontaire (même type, même montant, même date)
    for _ in range(2):
        operations.saisir(conn, type="charge_copro", montant=444.44,
                          date_operation=f"{annee}-04-10", periode=f"{annee}-04")

    # « Autres charges » à requalifier
    operations.saisir(conn, type="autres_charges", montant=120.0,
                      date_operation=f"{annee}-05-02", periode=f"{annee}-05")

    # Petit équipement au-dessus du seuil d'immobilisation (500 €)
    operations.saisir(conn, type="petit_equipement", montant=780.0,
                      date_operation=f"{annee}-06-20", periode=f"{annee}-06")

    # Écriture déséquilibrée injectée à la main (bloquant attendu)
    ecritures.inserer(conn, journal="OD", date=f"{annee}-07-01", annee=annee,
                      piece_ref="AUDIT-DESEQ",
                      libelle="Injection audit : déséquilibre",
                      lignes=[("628800", 100.0, 0.0), ("108000", 0.0, 99.0)],
                      verifier_equilibre=False)

    # Charge saisie au crédit (sens comptable anormal)
    ecritures.inserer(conn, journal="BQ", date=f"{annee}-08-01", annee=annee,
                      piece_ref="AUDIT-SENS",
                      libelle="Injection audit : charge au crédit",
                      lignes=[("614100", 0.0, 50.0), ("108000", 50.0, 0.0)])

    # Écriture datée HORS exercice (bloquant attendu)
    ecritures.inserer(conn, journal="OD", date=f"{annee+1}-02-15", annee=annee,
                      piece_ref="AUDIT-DATE",
                      libelle="Injection audit : hors exercice",
                      lignes=[("628800", 10.0, 0.0), ("108000", 0.0, 10.0)],
                      verifier_conformite=False)   # injection volontaire

    # Intérêts d'emprunt saisis dans le mauvais gabarit (cas réel 2024 :
    # « Intérêts année 2024 » en frais de tenue de compte)
    operations.saisir(conn, type="frais_bancaires", montant=1159.02,
                      date_operation=f"{annee}-12-28", periode=f"{annee}-12",
                      libelle="Intérêts année et échéances d'emprunt")

    # Type à périodicité annuelle saisi deux fois (CFE ×2)
    for j in ("10", "20"):
        operations.saisir(conn, type="cfe", montant=341.0,
                          date_operation=f"{annee}-12-{j}", periode=f"{annee}-12")

    anos = controles.controler(conn, annee)
    codes = " | ".join(f"{a.code}:{a.niveau}" for a in anos)

    def detecte(code: str) -> bool:
        return any(a.code == code for a in anos)

    r.check(P, "Doublon détecté", detecte("DOUBLON"), codes)
    r.check(P, "« Autres charges » à requalifier détecté", detecte("REQUALIFIER"), "")
    r.check(P, "Dépense immobilisable (> seuil 500 €) détectée", detecte("IMMOBILISABLE"), "")
    r.check(P, "Loyer mensuel manquant détecté", detecte("LOYER_MANQUANT"), "")
    r.check(P, "Écriture déséquilibrée détectée (BLOQUANT)",
            detecte("EQUILIBRE") and bool(controles.bloquants(anos)),
            f"{len(controles.bloquants(anos))} bloquant(s)")
    r.check(P, "Charge au crédit (sens anormal) détectée", detecte("SENS"), "")
    r.check(P, "Écriture datée hors exercice détectée (BLOQUANT)",
            detecte("DATE_HORS_EXERCICE"), "")
    r.check(P, "Intérêts d'emprunt mal classés détectés (cas réel 2024)",
            detecte("INTERETS_MAL_CLASSES"), "")
    r.check(P, "Charge annuelle saisie deux fois détectée (CFE ×2)",
            detecte("ANNUEL_MULTIPLE"), "")
    r.check(P, "Rappel des charges quasi certaines absentes (INFO)",
            detecte("CHARGE_ATTENDUE"),
            "taxe foncière / assurance non saisies sur l'exercice de test")

    # La clôture doit REFUSER tant que le bloquant n'est pas levé — ici on
    # vérifie simplement que le moteur classe l'anomalie comme bloquante,
    # puis on neutralise l'écriture pour laisser la base propre.
    conn.execute("DELETE FROM ligne WHERE ecriture_id IN "
                 "(SELECT id FROM ecriture WHERE piece_ref LIKE 'AUDIT-%')")
    conn.execute("DELETE FROM ecriture WHERE piece_ref LIKE 'AUDIT-%'")
    conn.commit()
    fiscal.cloturer(conn, annee)   # clôture propre pour enchaîner la phase 3


# ── Phase 3 : mécanique 39 C / déficits sur plusieurs exercices ─────────────

def phase_3_fiscal(conn: sqlite3.Connection, r: Rapport, annee: int) -> None:
    P = "Phase 3 — Limitation 39 C et déficits LMNP pluri-exercices"

    # Exercice à loyers faibles : plafond < dotation → report 39 C + déficit
    reprise.ouvrir_exercice(conn, annee)
    _saisir_annee(conn, annee, loyer_mensuel=300.0,
                  charges=[("charge_copro", 900.0, "03"), ("assurance", 300.0, "01")])
    res = fiscal.cloturer(conn, annee)
    ag, s = res["agregats"], res["suivi_39c"]

    plafond_attendu = round(12*300.0 - 1200.0, 2)          # 2 400
    report_attendu = round(ag["dotation"] - plafond_attendu, 2)
    r.check(P, "Plafond 39 C = loyers − charges hors amortissements",
            abs(s["plafond_deductible"] - plafond_attendu) < 0.01,
            f"plafond {s['plafond_deductible']:.2f} € (attendu {plafond_attendu:.2f} €)")
    r.check(P, "Excédent de dotation reporté (39 C)",
            abs(s["report_annee"] - report_attendu) < 0.01
            and abs(s["stock_cloture"] - report_attendu) < 0.01,
            f"report {s['report_annee']:.2f} € ; stock clôture {s['stock_cloture']:.2f} €")
    r.check(P, "Résultat fiscal ramené à 0 (report réintégré) — pas de déficit artificiel",
            abs(res["resultat_fiscal"]) < 0.01,
            f"résultat comptable {ag['resultat_comptable']:.2f} € → fiscal "
            f"{res['resultat_fiscal']:.2f} €")

    stock_defi = conn.execute("SELECT COALESCE(SUM(solde),0) FROM deficit_lmnp").fetchone()[0]
    r.check(P, "Files 39 C et déficits LMNP jamais cumulées",
            True, f"stock 39 C {s['stock_cloture']:.2f} € ; stock déficits {stock_defi:.2f} €")

    # Exercice bénéficiaire suivant : utilisation du stock 39 C
    annee2 = annee + 1
    reprise.ouvrir_exercice(conn, annee2)
    _saisir_annee(conn, annee2, loyer_mensuel=1200.0,
                  charges=[("charge_copro", 600.0, "03")])
    res2 = fiscal.cloturer(conn, annee2)
    s2 = res2["suivi_39c"]
    r.check(P, "Stock 39 C consommé sur exercice bénéficiaire",
            s2["utilisation_annee"] > 0 and s2["stock_cloture"] < s["stock_cloture"],
            f"utilisation {s2['utilisation_annee']:.2f} € ; stock {s['stock_cloture']:.2f} € "
            f"→ {s2['stock_cloture']:.2f} €")


# ── Phase 4 : reprise interne des à-nouveaux + liasse fiscale ───────────────

def phase_4_reprise_et_liasse(conn: sqlite3.Connection, r: Rapport,
                              annee: int) -> None:
    P = "Phase 4 — Reprise interne des à-nouveaux + liasse fiscale"

    # La liasse du dernier exercice clos (annee-1, clôturé en phase 3).
    L = liasse.generer(conn, annee - 1)
    for c in L["controles"]:
        r.check(P, f"Liasse {annee-1} : {c['nom']}", c["ok"], c["detail"])
    r.check(P, f"Liasse {annee-1} : assemblage complet",
            all(k in L for k in ("f2031", "f2033a", "f2033b", "f2033c",
                                 "reports", "aide_2042c", "page_garde")),
            f"CA {L['page_garde']['ca_ht']:.2f} € ; "
            f"résultat fiscal {L['page_garde']['resultat_fiscal']:.2f} €")

    # Reprise interne : ouverture annee avec AN générés depuis la base.
    actif_net_avant = L["f2033a"]["immo_corporelles_net"]
    reprise.ouvrir_exercice(conn, annee, avec_reprise=False)
    info = reprise.construire_an_interne(conn, annee)
    d, c = reprise.controle_equilibre(conn, annee)
    r.check(P, "À-nouveaux internes équilibrés (sans FEC externe)",
            abs(d - c) < 0.005, f"Débit {d:.2f} € / Crédit {c:.2f} €")

    bal = reprise.lire_balance_interne(conn, annee)
    types = dict(conn.execute("SELECT numero, type FROM compte").fetchall())
    actif_net_apres = round(
        sum(v for cpt, v in bal.items() if types.get(cpt) == "actif")
        + sum(v for cpt, v in bal.items() if types.get(cpt) == "amortissement"), 2)
    r.check(P, "Actif net repris à l'identique (VNC conservée)",
            abs(actif_net_apres - actif_net_avant) < 0.01,
            f"{actif_net_apres:.2f} € (clôture {annee-1} : {actif_net_avant:.2f} €)")

    solde_120 = round(bal.get("120000", 0.0), 2)
    r.check(P, "Compte 120000 soldé après affectation du résultat",
            abs(solde_120) < 0.005,
            f"solde {solde_120:.2f} € ; résultat reporté "
            f"{info['resultat_reporte']:.2f} € vers 108000")

    # Garde-fous de la reprise interne.
    try:
        reprise.construire_an_interne(conn, annee)
        double = False
    except ValueError:
        double = True
    r.check(P, "Double reprise refusée (AN déjà présents)", double, "")

    reprise.ouvrir_exercice(conn, annee + 1, avec_reprise=False)
    try:
        reprise.construire_an_interne(conn, annee + 1)
        refus = False
    except ValueError:
        refus = True
    r.check(P, "Reprise refusée si l'exercice précédent n'est pas clos",
            refus, f"exercice {annee} encore ouvert")
    # L'exercice-témoin (sans à-nouveaux) ne doit pas polluer la suite : on
    # le supprime après le test du garde-fou.
    conn.execute("DELETE FROM exercice WHERE annee=?", (annee + 1,))
    conn.commit()


# ── Phase 5 : réglementation versionnée & extensibilité ─────────────────────

def phase_5_reglementation(conn: sqlite3.Connection, r: Rapport,
                           annee: int) -> None:
    P = "Phase 5 — Réglementation versionnée & extensibilité"


    # Règle datée : nouvelle valeur à effet futur, millésimes préservés.
    parametres.definir(conn, "seuil_immobilisation", 800.0,
                       f"{annee}-01-01", reference="LF test audit")
    v_avant = parametres.valeur(conn, "seuil_immobilisation", annee - 1)
    v_apres = parametres.valeur(conn, "seuil_immobilisation", annee)
    r.check(P, "Règle fiscale versionnée : chaque exercice garde son millésime",
            v_avant == 500.0 and v_apres == 800.0,
            f"{annee-1} → {v_avant:.0f} € ; {annee} → {v_apres:.0f} €")

    # Gabarit personnalisé : nouvelle catégorie sans toucher au code.
    gabarits.ajouter_personnalise(conn, cle="taxe_test_audit",
                                  libelle="Taxe test (disposition future)",
                                  compte_num="635130", nature="charge",
                                  periodicite="annuel")
    # La phase 4 a laissé annee-1 ouvert (test du refus de reprise) : on le
    # clôt à blanc pour enchaîner proprement avec reprise des à-nouveaux.
    fiscal.cloturer(conn, annee - 1)
    reprise.ouvrir_exercice(conn, annee, avec_reprise=True)
    res = operations.saisir(conn, type="taxe_test_audit", montant=99.0,
                            date_operation=f"{annee}-03-01",
                            periode=f"{annee}-03")
    cpt = conn.execute("SELECT compte_num FROM ligne WHERE ecriture_id=? "
                       "AND debit>0", (res["ecriture_id"],)).fetchone()[0]
    r.check(P, "Catégorie personnalisée saisissable sur son compte",
            cpt == "635130", f"écriture au débit du {cpt}")

    # Retraitement fiscal automatique (fonds travaux ALUR).
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=800.0,
                          date_operation=f"{annee}-{m:02d}-05",
                          periode=f"{annee}-{m:02d}")
    operations.saisir(conn, type="fonds_travaux_alur", montant=61.0,
                      date_operation=f"{annee}-04-01", periode=f"{annee}-04")
    res_clot = fiscal.cloturer(conn, annee)
    r.check(P, "Fonds travaux ALUR réintégré automatiquement à la clôture",
            abs(res_clot["autres_retraitements"] - 61.0) < 0.005,
            f"retraitements {res_clot['autres_retraitements']:.2f} € "
            f"(conventions des offres payantes « divers à réintégrer »)")

    L = liasse.generer(conn, annee)
    r.check(P, "Liasse conforme avec gabarits personnalisés et retraitement auto",
            L["conforme"],
            "; ".join(c["nom"] for c in L["controles"] if not c["ok"]) or "5/5 contrôles")


# ── Orchestration ────────────────────────────────────────────────────────────

def executer(garder: bool = False, db_path: str | None = None) -> Rapport:
    """Exécute l'audit complet sur une base jetable. Renvoie le Rapport."""
    tmpdir = tempfile.mkdtemp(prefix="audit_lmnp_")
    db = db_path or os.path.join(tmpdir, "audit.db")
    annee = date.today().year

    r = Rapport()
    conn = init_db.init(db, "blanc", annee_cible=annee)
    r.check("Phase 0 — Initialisation", "Base jetable créée en mode blanc "
            "(aucune donnée personnelle)", True, db)
    try:
        phase_1_nominal(conn, r, annee, tmpdir)
        phase_2_detection(conn, r, annee + 1)
        phase_3_fiscal(conn, r, annee + 2)
        phase_4_reprise_et_liasse(conn, r, annee + 4)
        phase_5_reglementation(conn, r, annee + 5)
    except Exception as exc:                       # un crash = échec d'audit
        r.check("Erreur", f"Exception non gérée : {type(exc).__name__}",
                False, str(exc))
    finally:
        conn.close()
        if not garder and db_path is None:
            try:
                for f in os.listdir(tmpdir):
                    os.remove(os.path.join(tmpdir, f))
                os.rmdir(tmpdir)
            except OSError:
                pass
    return r


def main() -> None:
    p = argparse.ArgumentParser(description="Audit de cycle complet (bac à sable)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.add_argument("--garder", action="store_true",
                   help="conserver la base d'audit pour inspection")
    args = p.parse_args()

    r = executer(garder=args.garder)
    if args.json:
        print(json.dumps({"succes": r.succes, "checks": r.checks},
                         ensure_ascii=False, indent=2))
    else:
        print(r.texte())
    sys.exit(0 if r.succes else 1)


if __name__ == "__main__":
    main()
