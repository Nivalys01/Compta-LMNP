# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Tests J0 + J1 — non-régression contre les chiffres réels (clôture 2025 les acteurs payants actuels).
Lancer :  pytest -q
"""
import os
import pytest

import init_db

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEC = os.path.join(ROOT, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture(scope="module")
def conn():
    c = init_db.init_demo(os.path.join(ROOT, "test.db"), FEC, 2026)
    yield c
    c.close()
    os.remove(os.path.join(ROOT, "test.db"))


def solde(conn, compte):
    r = conn.execute(
        "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id WHERE l.compte_num=? AND e.exercice_annee=2026",
        (compte,),
    ).fetchone()
    return round(r[0], 2)


# --- J1 : référentiels ------------------------------------------------------

def test_seed_journaux(conn):
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 4

def test_seed_comptes(conn):
    assert conn.execute("SELECT COUNT(*) FROM compte").fetchone()[0] == 33

def test_seed_composants(conn):
    assert conn.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 14

def test_terrain_non_amortissable(conn):
    r = conn.execute("SELECT amortissable, duree_annees FROM composant "
                     "WHERE code_immo='MODYDX'").fetchone()
    assert r == (0, None)

def test_valeur_brute_totale(conn):
    # 139 908,66 € (terrain inclus) — valeurs EXACTES les acteurs payants actuels, pas arrondies.
    total = conn.execute("SELECT ROUND(SUM(valeur_brute),2) FROM composant").fetchone()[0]
    assert total == 139908.66


# --- J0 : reprise des à-nouveaux -------------------------------------------

def test_an_equilibre(conn):
    d, c = init_db.reprise.controle_equilibre(conn, 2026)
    assert d == c   # exercice (AN + OD affectation) équilibré

def test_chaque_ecriture_equilibree(conn):
    rows = conn.execute(
        "SELECT e.ecriture_num, ROUND(SUM(l.debit),2), ROUND(SUM(l.credit),2) "
        "FROM ligne l JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=2026 GROUP BY e.ecriture_num"
    ).fetchall()
    for num, d, c in rows:
        assert d == c, f"écriture {num} déséquilibrée: {d} != {c}"

def test_actif_net_egal_vnc_liasse(conn):
    # VNC bilan 2025 = 118 579 € ; ici au centime : 118 578,78.
    brut = solde(conn, "211550") + solde(conn, "213150") + solde(conn, "218100") + solde(conn, "218400")
    amort = solde(conn, "281315") + solde(conn, "281810") + solde(conn, "281840")
    assert round(brut + amort, 2) == 118578.78

def test_capitaux_propres_apres_affectation(conn):
    # Après l'OD d'affectation, 108000 doit égaler -VNC (capital = actif net).
    assert solde(conn, "108000") == -118578.78
    assert solde(conn, "120000") == 0.0   # résultat soldé par l'affectation


# --- Stocks fiscaux (deux files DISTINCTES) ---------------------------------

def test_stock_39c(conn):
    s = conn.execute("SELECT stock_cloture FROM suivi_39c WHERE exercice_annee=2025").fetchone()[0]
    assert s == 556.0

def test_deficits_total(conn):
    t = conn.execute("SELECT ROUND(SUM(solde),2) FROM deficit_lmnp").fetchone()[0]
    assert t == 13020.0

def test_deficits_ventiles_avec_peremption(conn):
    rows = conn.execute("SELECT annee_origine, annee_expiration FROM deficit_lmnp "
                        "ORDER BY annee_origine").fetchall()
    assert rows == [(2021, 2031), (2022, 2032), (2024, 2034), (2025, 2035)]

def test_39c_et_deficit_non_cumules(conn):
    # Garde-fou : les deux files ne doivent jamais être additionnées (≠ 14 867).
    stock = conn.execute("SELECT stock_cloture FROM suivi_39c WHERE exercice_annee=2025").fetchone()[0]
    deficits = conn.execute("SELECT SUM(solde) FROM deficit_lmnp").fetchone()[0]
    assert stock != deficits
    assert (stock, deficits) == (556.0, 13020.0)


# --- Export FEC (vue) -------------------------------------------------------

def test_vue_fec_18_colonnes(conn):
    cols = [d[0] for d in conn.execute("SELECT * FROM v_fec LIMIT 1").description]
    attendu = ["JournalCode","JournalLib","EcritureNum","EcritureDate","CompteNum",
               "CompteLib","CompAuxNum","CompAuxLib","PieceRef","PieceDate","EcritureLib",
               "Debit","Credit","EcritureLet","DateLet","ValidDate","Montantdevise","Idevise"]
    assert cols == attendu

def test_vue_fec_dates_aaaammjj(conn):
    d = conn.execute("SELECT EcritureDate FROM v_fec LIMIT 1").fetchone()[0]
    assert len(d) == 8 and d.isdigit()
