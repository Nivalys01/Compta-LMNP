# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Irritants documentés des logiciels de comptabilité (revue web pré-J9) :
1. « clôturé par erreur, impossible de déclôturer » (EBP, forums) →
   restauration en UN CLIC depuis l'interface (la sauvegarde avant-clôture
   est automatique depuis J6, l'UI manquait) ;
2. « base plus récente que l'application » (EBP) → garde de version de
   schéma avec message pédagogique, données intactes.
Lancer :  pytest -q tests/test_irritants.py
"""
import importlib
import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import init_db
import perennite

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod.app.test_client(), db
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_cloture_par_erreur_reversible_en_un_clic(client):
    c, db = client
    sv = perennite.sauvegarder(db, "avant-cloture")
    c.post("/cloturer", data={"annee": "2026", "forcer": "1"})
    assert sqlite3.connect(db).execute(
        "SELECT statut FROM exercice WHERE annee=2026").fetchone()[0] == "clos"
    r = c.post("/sauvegardes/restaurer", data={"nom": os.path.basename(sv)},
               follow_redirects=True)
    assert r.status_code == 200
    assert sqlite3.connect(db).execute(
        "SELECT statut FROM exercice WHERE annee=2026").fetchone()[0] == "ouvert"


def test_restauration_nom_hostile_rejetee(client):
    c, _db = client
    r = c.post("/sauvegardes/restaurer",
               data={"nom": "../../../etc/passwd"}, follow_redirects=True)
    assert r.status_code == 200                      # message d'erreur propre
    assert "Restauration refusée" in r.get_data(as_text=True)


def test_base_plus_recente_message_pedagogique(client):
    c, db = client
    c.get("/")                                       # marque la version
    cx = sqlite3.connect(db)
    cx.execute("UPDATE meta SET valeur='999' WHERE cle='version_schema'")
    cx.commit()
    cx.close()
    r = c.get("/")
    assert r.status_code == 409
    assert "plus récente du logiciel" in r.get_data(as_text=True)


def test_version_jamais_abaissee(client):
    _c, db = client
    cx = sqlite3.connect(db)
    init_db.marquer_version(cx)
    cx.execute("UPDATE meta SET valeur='2' WHERE cle='version_schema'")
    cx.commit()
    init_db.marquer_version(cx)                      # remonte, n'abaisse pas
    assert init_db.version_base(cx) == init_db.VERSION_SCHEMA
    cx.close()
