# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
# sans autorisation écrite de l'auteur.

"""
Tests des modes d'amorçage : 'blanc' (produit livré) vs 'demo' (exemple).
Lancer :  pytest -q
"""
import os
import pytest

import init_db
import operations

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEC2025 = os.path.join(ROOT, "reference", "FEC_REFERENCE_2025.txt")


def compte(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# --- Mode blanc : produit livré, aucune donnée personnelle ------------------

def test_blanc_referentiel_present(tmp_path):
    conn = init_db.init_blanc(str(tmp_path / "b.db"), 2026)
    assert compte(conn, "journal") == 4
    assert compte(conn, "compte") == 38     # +5 comptes, passe E (E-10)
    conn.close()

def test_blanc_aucune_donnee_personnelle(tmp_path):
    conn = init_db.init_blanc(str(tmp_path / "b.db"), 2026)
    assert compte(conn, "exploitant") == 0
    assert compte(conn, "bien") == 0
    assert compte(conn, "composant") == 0
    assert compte(conn, "operation") == 0
    assert compte(conn, "ecriture") == 0       # pas de reprise : aucune écriture
    assert compte(conn, "suivi_39c") == 0
    assert compte(conn, "deficit_lmnp") == 0
    conn.close()

def test_blanc_exercice_ouvert_pret(tmp_path):
    conn = init_db.init_blanc(str(tmp_path / "b.db"), 2027)
    ex = conn.execute("SELECT annee, statut FROM exercice").fetchall()
    assert ex == [(2027, "ouvert")]
    conn.close()

def test_blanc_saisie_possible_immediatement(tmp_path):
    # Un nouveau dossier doit pouvoir saisir dès l'init (1re écriture = n°1).
    conn = init_db.init_blanc(str(tmp_path / "b.db"), 2026)
    r = operations.saisir(conn, type="loyer", montant=650, date_operation="2026-01-05",
                          periode="2026-01", bien_id=None)
    assert r["ecriture_num"] == 1
    conn.close()


# --- Mode demo : exemple complet avec reprise -------------------------------

def test_demo_charge_exemple_et_reprise(tmp_path):
    conn = init_db.init_demo(str(tmp_path / "d.db"), FEC2025, 2026)
    assert compte(conn, "composant") == 14
    assert compte(conn, "deficit_lmnp") == 4
    # La reprise a bien créé l'AN + l'OD d'affectation.
    # La démo porte désormais un exercice PRÉCÉDENT complet (rejeu du FEC)
    # en plus des à-nouveaux de l'exercice courant : un débutant doit voir
    # à quoi ressemble une année de location tenue de bout en bout.
    assert compte(conn, "ecriture") > 30
    n_2025 = conn.execute("SELECT COUNT(*) FROM ecriture "
                          "WHERE exercice_annee=2025").fetchone()[0]
    assert n_2025 >= 30
    assert conn.execute("SELECT COUNT(*) FROM ecriture WHERE "
                        "exercice_annee=2026 AND journal_code='AN'"
                        ).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM operation WHERE "
                        "exercice_annee=2025").fetchone()[0] >= 20
    conn.close()


def test_mode_inconnu_rejete(tmp_path):
    with pytest.raises(ValueError):
        init_db.init(str(tmp_path / "x.db"), "exemple")
