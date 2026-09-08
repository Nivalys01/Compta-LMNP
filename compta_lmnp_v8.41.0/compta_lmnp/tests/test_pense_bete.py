# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Pense-bête — rappels manuels selon échéances et événements.
Lancer :  pytest -q tests/test_pense_bete.py
"""
import os
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import fiscal
import init_db
import operations
import pense_bete

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "p.db"), FEC2025, 2026)
    yield c
    c.close()


def _titres(rappels):
    return " | ".join(r["titre"] for r in rappels)


def test_exercice_precedent_ouvert_en_mai(conn):
    r = pense_bete.rappels(conn, date(2027, 5, 10))
    assert "Clôturer l'exercice 2026" in _titres(r)


def test_exercice_clos_periode_declarative(conn):
    fiscal.cloturer(conn, 2026)
    r = pense_bete.rappels(conn, date(2027, 4, 2))
    assert "Déclarer les résultats 2026" in _titres(r)
    # hors période déclarative : le rappel disparaît
    r2 = pense_bete.rappels(conn, date(2027, 9, 1))
    assert "Déclarer les résultats" not in _titres(r2)


def test_cfe_en_decembre(conn):
    r = pense_bete.rappels(conn, date(2026, 12, 3))
    assert "CFE avant le 15 décembre" in _titres(r)


def test_bien_acquis_dans_l_annee_declenche_formalites(conn):
    exp = conn.execute("SELECT id FROM exploitant LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition)"
                 " VALUES (?, 'T2 Vichy', '2026-03-15')", (exp,))
    conn.commit()
    r = pense_bete.rappels(conn, date(2026, 7, 1))
    assert "T2 Vichy" in _titres(r)
    assert any("INPI" in x["detail"] and "1447-C" in x["detail"] for x in r)


def test_seuil_lmp_23000(conn):
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=2100,
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    r = pense_bete.rappels(conn, date(2026, 11, 2))
    assert "seuil LMP" in _titres(r)


def test_alur_manquant_si_charges_copro(conn):
    operations.saisir(conn, type="charge_copro", montant=480,
                      date_operation="2026-04-10", bien_id=1)
    r = pense_bete.rappels(conn, date(2026, 6, 1))
    assert "ALUR" in _titres(r)
    # une fois saisi, le rappel s'éteint
    operations.saisir(conn, type="fonds_travaux_alur", montant=61,
                      date_operation="2026-04-10", bien_id=1)
    r2 = pense_bete.rappels(conn, date(2026, 6, 1))
    assert "ALUR" not in _titres(r2)
