# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Tests J4 (amortissement) + J5 (39 C & déficits LMNP).
Lancer :  pytest -q
"""
import os
import pytest

import init_db
import operations
import amortissement as am
import fiscal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEC2025 = os.path.join(ROOT, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "d.db"), FEC2025, 2026)
    yield c
    c.close()


# === J4 — amortissement ====================================================

@pytest.mark.parametrize("vb,duree,dms,annee,attendu", [
    (58500.00, 55, "2021-11-01", 2025, 1063.64),   # gros oeuvre, plein
    (29905.20, 25, "2021-11-01", 2025, 1196.21),
    (19995.30, 25, "2021-11-01", 2025,  799.81),
    (1666.50,  20, "2021-11-01", 2025,   83.33),
    (2517.59,   5, "2021-11-01", 2025,  503.52),   # mobilier 5 ans, plein
])
def test_dotation_reproduit_les_liasses_reelles(vb, duree, dms, annee, attendu):
    dot, _, _ = am.etat(vb, duree, dms, annee)
    assert dot == attendu

def test_prorata_annee_entree():
    # Prorata en JOURS RÉELS (convention prouvée contre les liasses de référence) :
    # du 01/11 au 31/12 inclus = 61 jours sur 365.
    dot, _, _ = am.etat(58500.00, 55, "2021-11-01", 2021)
    assert dot == round(1063.64 * 61 / 365, 2)

def test_meuble_5ans_finit_en_2026():
    # Mobilier chambres : plein en 2025, plafonné en 2026, nul en 2027.
    d25, _, _ = am.etat(2517.59, 5, "2021-11-01", 2025)
    d26, c26, vnc26 = am.etat(2517.59, 5, "2021-11-01", 2026)
    d27, _, _ = am.etat(2517.59, 5, "2021-11-01", 2027)
    # d26 = solde restant après le prorata en jours de 2021 (61/365).
    assert d25 == 503.52 and d26 == 419.36 and d27 == 0.0
    assert c26 == 2517.59 and vnc26 == 0.0     # entièrement amorti fin 2026

def test_terrain_jamais_amorti(conn):
    dots = {d["libelle"]: d for d in am.dotations_exercice(conn, 2026)}
    assert "Terrain" not in dots

def test_dotation_2026_inferieure_a_2025(conn):
    total = am.generer_cloture(conn, 2026)["total"]
    assert total == 4983.47          # < 5183.97 : meubles 5 ans en fin de plan

def test_cloture_genere_od_equilibree(conn):
    r = am.generer_cloture(conn, 2026)
    d, c = conn.execute(
        "SELECT SUM(debit), SUM(credit) FROM ligne WHERE ecriture_id=?",
        (r["ecriture_id"],)).fetchone()
    assert round(d, 2) == round(c, 2) == r["total"]

def test_plan_amortissement_trace(conn):
    am.generer_cloture(conn, 2026)
    n = conn.execute("SELECT COUNT(*) FROM plan_amortissement WHERE exercice_annee=2026").fetchone()[0]
    assert n == 13     # 13 composants amortissables (terrain exclu)


# === J5 — limitation 39 C (logique pure) ===================================

def test_39c_report_quand_dotation_depasse_plafond():
    # 2024 réel : dotation 5184 > plafond 4887 -> report 297.
    s = fiscal.calculer_39c(stock_ouverture=0, dotation=5184, plafond=4887)
    assert s["report_annee"] == 297.0 and s["utilisation_annee"] == 0.0
    assert s["stock_cloture"] == 297.0

def test_39c_cumul_2025():
    # Enchaînement 2025 : stock 297 + report (5183.97-4926).
    s = fiscal.calculer_39c(stock_ouverture=297, dotation=5183.97, plafond=4926)
    assert s["report_annee"] == 257.97
    assert s["stock_cloture"] == 554.97

def test_39c_utilisation_quand_plafond_suffisant():
    # Plafond large : on déduit le stock antérieur dans la limite.
    s = fiscal.calculer_39c(stock_ouverture=556, dotation=4984, plafond=6000)
    assert s["report_annee"] == 0.0
    assert s["utilisation_annee"] == 556.0
    assert s["stock_cloture"] == 0.0


# === J5 — déficits LMNP (FIFO + péremption) ================================

def test_deficit_nouveau_millesime(conn):
    r = fiscal.traiter_deficit(conn, 2026, resultat_fiscal=-630)
    assert r["deficit_cree"] == 630.0
    exp = conn.execute("SELECT annee_expiration FROM deficit_lmnp WHERE annee_origine=2026").fetchone()[0]
    assert exp == 2036

def test_deficit_imputation_fifo(conn):
    # Bénéfice 1000 -> impute sur le plus ancien (2021) d'abord.
    avant_2021 = conn.execute("SELECT solde FROM deficit_lmnp WHERE annee_origine=2021").fetchone()[0]
    r = fiscal.traiter_deficit(conn, 2026, resultat_fiscal=1000)
    apres_2021 = conn.execute("SELECT solde FROM deficit_lmnp WHERE annee_origine=2021").fetchone()[0]
    assert r["impute_sur_benefice"] == 1000.0
    assert round(avant_2021 - apres_2021, 2) == 1000.0

def test_deficit_peremption_10_ans(conn):
    # Un déficit 2014 (périmé en 2024) doit être purgé lors d'une clôture 2026.
    conn.execute("INSERT INTO deficit_lmnp (annee_origine, montant_initial, solde, annee_expiration) "
                 "VALUES (2014, 500, 500, 2024)")
    conn.commit()
    fiscal.traiter_deficit(conn, 2026, resultat_fiscal=0)
    solde = conn.execute("SELECT solde FROM deficit_lmnp WHERE annee_origine=2014").fetchone()[0]
    assert solde == 0


# === J5 — clôture intégrale (scénario contrôlé) ============================

def test_cloture_complete_scenario_benefice(conn):
    # Scénario maîtrisé : loyers 10000, charges 1000, dotation 2026 = 4983,47.
    operations.saisir(conn, type="loyer", montant=10000, date_operation="2026-01-05", periode="2026-01")
    operations.saisir(conn, type="charge_copro", montant=1000, date_operation="2026-02-05")
    res = fiscal.cloturer(conn, 2026)

    assert res["agregats"]["dotation"] == 4983.47
    assert res["agregats"]["plafond_39c"] == 9000.00            # 10000-1000
    # Cohérence interne : résultat comptable = produits - charges - dotation.
    assert res["agregats"]["resultat_comptable"] == round(10000 - 1000 - 4983.47, 2)
    # 39C : dotation < plafond -> on consomme le stock d'ouverture 556.
    assert res["suivi_39c"]["utilisation_annee"] == 556.0
    assert res["suivi_39c"]["stock_cloture"] == 0.0
    # Résultat fiscal = comptable + report - utilisation.
    rf = round(res["agregats"]["resultat_comptable"] + res["suivi_39c"]["report_annee"]
               - res["suivi_39c"]["utilisation_annee"], 2)
    assert res["resultat_fiscal"] == rf and rf > 0          # bénéfice
    # Bénéfice imputé FIFO : 13020 - bénéfice.
    assert res["deficits"]["stock_deficits"] == round(13020 - rf, 2)
    solde_2021 = conn.execute("SELECT solde FROM deficit_lmnp WHERE annee_origine=2021").fetchone()[0]
    assert solde_2021 == round(11520 - rf, 2)

def test_cloture_complete_scenario_deficit(conn):
    # Charges > loyers -> vrai déficit d'exploitation ; toute la dotation est reportée.
    operations.saisir(conn, type="loyer", montant=1000, date_operation="2026-01-05", periode="2026-01")
    operations.saisir(conn, type="charge_copro", montant=2000, date_operation="2026-02-05")
    res = fiscal.cloturer(conn, 2026, autres_retraitements=0)
    # Plafond négatif (1000-2000) -> report = toute la dotation, jamais plus.
    assert res["suivi_39c"]["report_annee"] == res["agregats"]["dotation"]
    assert res["resultat_fiscal"] < 0          # déficit réel (issu des charges)
    assert res["deficits"]["deficit_cree"] == round(-res["resultat_fiscal"], 2)
    exp = conn.execute("SELECT annee_expiration FROM deficit_lmnp WHERE annee_origine=2026").fetchone()[0]
    assert exp == 2036
    assert res["suivi_39c"]["stock_cloture"] > 556          # le stock 39C a grossi
