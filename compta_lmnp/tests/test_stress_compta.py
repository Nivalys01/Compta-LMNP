# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Stress test du moteur comptable — campagne figée en non-régression.
Failles corrigées par cette campagne :
  1. saisie possible dans un exercice CLOS (rien ne la détectait après coup) ;
  2. clôtures acceptées dans le désordre (N+1 avant N → reports faussés) ;
  3. échec d'insertion laissant un en-tête d'écriture ORPHELIN dans la
     transaction (trou de numérotation FEC au commit suivant).
Lancer :  pytest -q tests/test_stress_compta.py
"""
import os
import random
import subprocess
import sys

import conftest

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import ecritures
import export_fec
import fiscal
import init_db
import operations
import reprise

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")
CONTREPARTIE, LOYERS = "108000", "708810"


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "d.db"), FEC2025, 2026)
    yield c
    c.close()


# === Faille n°1 : exercice clos scellé =====================================

def test_saisie_refusee_dans_exercice_clos(conn):
    fiscal.cloturer(conn, 2026, forcer=True)
    with pytest.raises(ValueError, match="clos"):
        operations.saisir(conn, type="loyer", montant=795,
                          date_operation="2026-11-01", exercice=2026, bien_id=1)
    with pytest.raises(ValueError, match="clos"):
        ecritures.inserer(conn, journal="OD", date="2026-11-02", annee=2026,
                          libelle="intrusion",
                          lignes=[(CONTREPARTIE, 10, 0), (LOYERS, 0, 10)])


def test_ecriture_exercice_inconnu_message_clair(conn):
    with pytest.raises(ValueError, match="inconnu"):
        ecritures.inserer(conn, journal="BQ", date="2099-01-01", annee=2099,
                          libelle="x",
                          lignes=[(CONTREPARTIE, 10, 0), (LOYERS, 0, 10)])


# === Faille n°2 : ordre chronologique des clôtures =========================

def test_cloture_refusee_dans_le_desordre(conn):
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                 "VALUES (2027,'2027-01-01','2027-12-31','ouvert')")
    conn.commit()
    with pytest.raises(ValueError, match="2026"):
        fiscal.cloturer(conn, 2027)
    fiscal.cloturer(conn, 2026)          # puis l'ordre légitime passe
    fiscal.cloturer(conn, 2027, forcer=True)


# === Faille n°3 : pas d'en-tête orphelin après un échec ====================

def test_echec_insertion_ne_laisse_aucune_ecriture_orpheline(conn):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        ecritures.inserer(conn, journal="BQ", date="2026-03-01", annee=2026,
                          libelle="rate",
                          lignes=[("999999", 100, 0), (LOYERS, 0, 100)])
    conn.commit()                        # commit ultérieur sans rapport
    orphelines = conn.execute(
        "SELECT COUNT(*) FROM ecriture e WHERE NOT EXISTS "
        "(SELECT 1 FROM ligne l WHERE l.ecriture_id = e.id)").fetchone()[0]
    assert orphelines == 0
    # …et la numérotation reste dense : la prochaine écriture prend le
    # numéro que l'échec aurait consommé.
    avant = ecritures.prochain_num(conn, 2026)
    r = ecritures.inserer(conn, journal="BQ", date="2026-03-02", annee=2026,
                          libelle="ok",
                          lignes=[(CONTREPARTIE, 10, 0), (LOYERS, 0, 10)])
    assert r["ecriture_num"] == avant


def test_injection_sql_dans_libelle_inerte(conn):
    r = ecritures.inserer(conn, journal="BQ", date="2026-03-01", annee=2026,
                          libelle="'; DROP TABLE ecriture;--",
                          lignes=[(CONTREPARTIE, 1, 0), (LOYERS, 0, 1)])
    stocke = conn.execute("SELECT libelle FROM ecriture WHERE id=?",
                          (r["ecriture_id"],)).fetchone()[0]
    assert stocke == "'; DROP TABLE ecriture;--"
    assert conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] > 0


# === Marathon condensé : 5 exercices avec hostilités =======================

def test_marathon_5_exercices_hostiles(conn, tmp_path):
    random.seed(42)
    for annee in range(2026, 2031):
        for mois in range(1, 13):
            operations.saisir(conn, type="loyer",
                              montant=795 + random.randint(0, 99) / 100,
                              date_operation=f"{annee}-{mois:02d}-05", bien_id=1)
        if annee > 2026:                 # hostilité : saisie dans N-1 clos
            with pytest.raises(ValueError):
                operations.saisir(conn, type="loyer", montant=100,
                                  date_operation=f"{annee-1}-06-01",
                                  exercice=annee - 1, bien_id=1)
        with pytest.raises(ValueError):  # hostilité : déséquilibre d'un centime
            ecritures.inserer(conn, journal="OD", date=f"{annee}-06-30",
                              annee=annee, libelle="piège",
                              lignes=[(CONTREPARTIE, 500, 0),
                                      (LOYERS, 0, 499.99)])
        fiscal.cloturer(conn, annee, forcer=True)
        d, c = reprise.controle_equilibre(conn, annee)
        assert abs(d - c) <= 0.005       # bilan équilibré chaque année
        if annee < 2030:
            reprise.ouvrir_exercice(conn, annee + 1)

    # Le FEC du dernier exercice passe le validateur indépendant.
    fec = str(tmp_path / "FEC2030.txt")
    export_fec.exporter(conn, 2030, fec)
    r = subprocess.run([sys.executable, conftest.source("valider_fec.py"),
                        fec], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# === Volume (version CI : 300 opérations) ==================================

def test_volume_300_operations_equilibre_exact(conn, tmp_path):
    random.seed(1789)
    types_charges = ["assurance", "energie", "telecom", "maintenance"]
    for i in range(300):
        jour = f"2026-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        if i % 3 == 0:
            operations.saisir(conn, type="loyer",
                              montant=round(random.uniform(500, 900), 2),
                              date_operation=jour, bien_id=1)
        else:
            operations.saisir(conn, type=random.choice(types_charges),
                              montant=round(random.uniform(5, 400), 2),
                              date_operation=jour, bien_id=1)
    fiscal.cloturer(conn, 2026, forcer=True)
    d, c = reprise.controle_equilibre(conn, 2026)
    assert abs(d - c) < 0.005            # pas un centime perdu en route
    fec = str(tmp_path / "FEC.txt")
    export_fec.exporter(conn, 2026, fec)
    r = subprocess.run([sys.executable, conftest.source("valider_fec.py"),
                        fec], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
